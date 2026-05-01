"""
去重性能基准测试。

测量不同历史记录规模下，去重各阶段的耗时分布：
  - Stage 1: 精确 URL 匹配
  - Stage 2: 精确标题匹配
  - Stage 3: 标题相似度匹配
  - Stage 4: 语义向量（余弦相似度）

Usage:
    python benchmark_dedup.py                          # 默认：mock 模式 + 小规模
    python benchmark_dedup.py --mock                   # mock 向量（不调 API，仅测计算）
    python benchmark_dedup.py --real --model text-embedding-v3  # 调真实 embedding API
    python benchmark_dedup.py --sizes 100 500 1000 5000        # 自定义规模
    python benchmark_dedup.py --items 10               # 每次测试的待检 item 数
"""

import argparse
import math
import random
import sys
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

# 保证能导入项目内的模块
_project_root = Path(__file__).resolve().parent.parent
_pkg_dir = _project_root / "wechat_edu_agent"
sys.path.insert(0, str(_pkg_dir))

from models.schemas import NewsItem
from search.dedup import (
    SearchHistory,
    HistoryRecord,
    DedupDecision,
    cosine_similarity,
    normalize_title,
    normalize_url,
    title_similarity_score,
)
from config import load_config
from llm.client import LLMClient


# ─────────────── 随机新闻生成器 ───────────────

NEWS_TEMPLATES = [
    {"title": "教育部发布{year}年{topic}新政策", "source": "教育部官网", "summary": "教育部近日发布了关于{topic}的最新政策文件，要求各地区严格执行。"},
    {"title": "{city}{topic}改革试点取得阶段性成果", "source": "中国教育报", "summary": "经过一年的{topic}改革试点，{city}取得了显著成效。"},
    {"title": "专家解读{topic}新规：{comment}", "source": "新华网", "summary": "多位教育专家对{topic}新规进行了解读，认为{comment}。"},
    {"title": "{city}中小学{topic}实施方案公布", "source": "地方教育局", "summary": "{city}教育局公布了中小学{topic}的具体实施方案。"},
    {"title": "聚焦{topic}：{year}年教育工作会议召开", "source": "人民日报", "summary": "{year}年全国教育工作会议在京召开，{topic}成为会议焦点。"},
    {"title": "家长热议{topic}：{comment}", "source": "澎湃新闻", "summary": "关于{topic}的话题在家长群体中引发热议，不少家长表示{comment}。"},
    {"title": "{city}率先开展{topic}专项行动", "source": "央视新闻", "summary": "{city}在全市范围内率先开展了{topic}专项行动。"},
    {"title": "全国{topic}推进情况年度报告发布", "source": "教育部", "summary": "{year}年度全国{topic}推进情况报告正式对外发布。"},
    {"title": "政协委员建议{topic}纳入考核体系", "source": "光明日报", "summary": "在全国政协会议上，多位委员提议将{topic}纳入考核体系。"},
    {"title": "教育局长谈{topic}：未来三年规划", "source": "中国教育电视台", "summary": "多位教育局负责人就{topic}的未来三年规划进行了介绍。"},
]

TOPICS = ["减负", "内卷", "素质教育", "双减", "课后服务", "职业教育", "高考改革", "学前教育", "家庭教育", "教师减负"]
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "长沙"]
COMMENTS = [
    "有利于学生全面发展",
    "需要家校社会共同努力",
    "政策落地仍需时日",
    "将有效缓解教育焦虑",
    "实施细节还需进一步完善",
    "对促进教育公平有重要意义",
]


def random_news_item(seed: int) -> NewsItem:
    rng = random.Random(seed)
    template = rng.choice(NEWS_TEMPLATES)
    topic = rng.choice(TOPICS)
    city = rng.choice(CITIES)
    comment = rng.choice(COMMENTS)
    year = rng.choice([2024, 2025, 2026])

    title = template["title"].format(year=year, topic=topic, city=city, comment=comment)
    source = template["source"]
    summary = template["summary"].format(year=year, topic=topic, city=city, comment=comment)

    # 50% 概率带 URL，50% 概率为 manual:// 以模拟真实数据分布
    if rng.random() < 0.5:
        slug = title.replace(" ", "")[:10]
        url = f"https://news.example.com/{year}/{slug}"
    else:
        url = "manual://"

    return NewsItem(
        news_type=rng.choice(["教育部政策", "学校案例", "社会事件"]),
        title=title,
        source=source,
        published_at=f"{year}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
        url=url,
        summary=summary,
        core_facts=[f"{topic}相关政策正在推进中", f"{city}已开始试点"],
        parent_emotion_points=[f"{topic}引发{comment}", "社会关注度持续上升"],
        relevance_score=rng.randint(60, 100),
        virality_score=rng.randint(50, 95),
        reason=f"关于{topic}的{source}报道",
    )


# ─────────────── 计时工具 ───────────────

@dataclass
class TimingResult:
    stage: str
    elapsed_ms: float
    records_scanned: int
    detail: str = ""


class TimedSearchHistory(SearchHistory):
    """在 SearchHistory 基础上包装计时逻辑的子类。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timing_log: list[TimingResult] = []
        self._stage_timings: dict[str, list[float]] = {
            "url_exact": [],
            "title_exact": [],
            "title_similarity": [],
            "vector_similarity": [],
        }

    def classify_with_timing(self, item: NewsItem, current_batch: list[HistoryRecord]) -> DedupDecision:
        """带逐阶段计时的 _classify_item 逻辑复制。"""
        item_title = item.title.strip()
        item_source = item.source.strip()
        item_url = item.url.strip()
        item_title_key = normalize_title(item_title)
        item_url_key = normalize_url(item_url)

        comparison_records = [*self.records]
        comparison_records.extend(current_batch)
        total_records = len(comparison_records)

        # ── Stage 1: 精确 URL ──
        t0 = time.perf_counter()
        for record in comparison_records:
            if item_url_key and record.url_key and item_url_key == record.url_key:
                elapsed = (time.perf_counter() - t0) * 1000
                self._stage_timings["url_exact"].append(elapsed)
                return DedupDecision(
                    title=item_title, source=item_source, url=item_url,
                    duplicate=True, reason="exact url match",
                    matched_title=record.title, matched_source=record.source, matched_url=record.url,
                )
        elapsed_s1 = (time.perf_counter() - t0) * 1000
        self._stage_timings["url_exact"].append(elapsed_s1)

        # ── Stage 2: 精确标题 ──
        t0 = time.perf_counter()
        for record in comparison_records:
            if item_title_key and record.title_key and item_title_key == record.title_key:
                elapsed = (time.perf_counter() - t0) * 1000
                self._stage_timings["title_exact"].append(elapsed)
                return DedupDecision(
                    title=item_title, source=item_source, url=item_url,
                    duplicate=True, reason="exact title match",
                    matched_title=record.title, matched_source=record.source, matched_url=record.url,
                )
        elapsed_s2 = (time.perf_counter() - t0) * 1000
        self._stage_timings["title_exact"].append(elapsed_s2)

        # ── Stage 3: 标题相似度 ──
        t0 = time.perf_counter()
        for record in comparison_records:
            title_sim = title_similarity_score(item_title, record.title)
            if title_sim >= self.title_threshold:
                elapsed = (time.perf_counter() - t0) * 1000
                self._stage_timings["title_similarity"].append(elapsed)
                return DedupDecision(
                    title=item_title, source=item_source, url=item_url,
                    duplicate=True, reason="title similarity match",
                    matched_title=record.title, matched_source=record.source,
                    matched_url=record.url, title_similarity=title_sim,
                )
        elapsed_s3 = (time.perf_counter() - t0) * 1000
        self._stage_timings["title_similarity"].append(elapsed_s3)

        # ── Stage 4: 语义向量 ──
        t0 = time.perf_counter()
        # 为当前 item 获取向量（对 benchmark，向量已在外部设置）
        item_vector = self._get_item_vector(item)
        if item_vector and item_vector is not True:
            best_score = 0.0
            best_record: HistoryRecord | None = None
            for record in comparison_records:
                if not record.vector:
                    continue
                score = cosine_similarity(item_vector, record.vector)
                threshold = self._threshold_for_record(record)
                if score >= threshold and score > best_score:
                    best_score = score
                    best_record = record

            if best_record:
                elapsed = (time.perf_counter() - t0) * 1000
                self._stage_timings["vector_similarity"].append(elapsed)
                return DedupDecision(
                    title=item_title, source=item_source, url=item_url,
                    duplicate=True, reason="semantic similarity match",
                    matched_title=best_record.title, matched_source=best_record.source,
                    matched_url=best_record.url, similarity=best_score,
                    age_days=self._age_days(best_record.published_at),
                )
        elapsed_s4 = (time.perf_counter() - t0) * 1000
        self._stage_timings["vector_similarity"].append(elapsed_s4)

        return DedupDecision(
            title=item_title, source=item_source, url=item_url,
            duplicate=False, reason="unique",
        )

    def _get_item_vector(self, item: NewsItem) -> list[float] | None:
        """获取 item 的向量。如果是 mock 模式则在 self 上缓存。"""
        if hasattr(self, "_mock_vectors"):
            semantic_text = self._build_semantic_text(item)
            h = hash(semantic_text)
            if h in self._mock_vectors:
                return self._mock_vectors[h]
            return None
        # 真实模式：调用 API（但 benchmark 中我们预置向量，不重复调用）
        return None

    def _load_or_build_mock_vectors(self, records: list[HistoryRecord], dim: int = 128):
        """为所有记录生成 mock 向量（低维加速测试，不影响相对耗时）。"""
        self._mock_vectors = {}
        for r in records:
            if r.vector:
                key = hash(r.semantic_text)
                self._mock_vectors[key] = r.vector


# ─────────────── Benchmark 核心 ───────────────

def build_history(history_size: int, llm_client: LLMClient | None) -> list[HistoryRecord]:
    """构建指定大小的历史记录（含向量）。"""
    records: list[HistoryRecord] = []
    batch_size = 50
    for i in range(0, history_size, batch_size):
        current_batch = min(batch_size, history_size - i)
        items = [random_news_item(seed=100000 + i + j) for j in range(current_batch)]
        texts = [SearchHistory._build_semantic_text(item) for item in items]

        if llm_client and texts:
            try:
                vectors = llm_client.embed_texts(texts)
            except Exception:
                vectors = []
        else:
            vectors = []

        for j, item in enumerate(items):
            vec = vectors[j] if j < len(vectors) else None
            record = HistoryRecord(
                title=item.title.strip(),
                source=item.source.strip(),
                url=item.url.strip(),
                published_at=item.published_at.strip(),
                searched_at=datetime.now().isoformat(timespec="seconds"),
                semantic_text=SearchHistory._build_semantic_text(item),
                content_hash=SearchHistory._hash_text(SearchHistory._build_semantic_text(item)),
                title_key=normalize_title(item.title),
                url_key=normalize_url(item.url),
                vector=vec,
            )
            records.append(record)
    return records


def run_benchmark(
    history_size: int,
    test_items_count: int,
    llm_client: LLMClient | None,
    mock: bool = True,
    verbose: bool = False,
):
    print(f"\n{'='*60}")
    print(f"历史记录数: {history_size}  |  测试 item 数: {test_items_count}")
    print(f"向量模式: {'Mock (128d)' if mock else '真实 API'}")
    print(f"{'='*60}")

    # 1. 构建历史记录
    t0 = time.perf_counter()
    history_records = build_history(history_size, llm_client)
    build_ms = (time.perf_counter() - t0) * 1000
    print(f"构建历史: {len(history_records)} 条, 耗时 {build_ms:.1f}ms")

    # 2. 构造 TimedSearchHistory（不读取磁盘文件）
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="dedup_bench_"))
    deduper = TimedSearchHistory(
        store_dir=tmp_dir,
        llm_client=llm_client,
        embedding_model=llm_client.embedding_model if llm_client else None,
        similarity_threshold=0.86,
        title_threshold=0.8,
        recent_days=30,
    )
    # 用已构建的记录替换空 records
    deduper.records = history_records
    if mock:
        deduper._load_or_build_mock_vectors(history_records, dim=128)

    # 3. 生成测试 items
    test_items = [random_news_item(seed=i) for i in range(test_items_count)]

    # 4. 如果需要真实向量，为测试 items 预获取向量
    if not mock and llm_client:
        print("正在获取测试 items 的向量...")
        for item in test_items:
            text = deduper._build_semantic_text(item)
            try:
                vec = llm_client.embed_text(text)
            except Exception:
                vec = None
            # 暂存在 _mock_vectors 上用 hash 索引（复用 mock 机制）
            if not hasattr(deduper, "_mock_vectors"):
                deduper._mock_vectors = {}
            deduper._mock_vectors[hash(text)] = vec

    # 5. 执行计时去重
    t0 = time.perf_counter()
    kept = 0
    dropped = 0
    for item in test_items:
        decision = deduper.classify_with_timing(item, [])
        if decision.duplicate:
            dropped += 1
        else:
            kept += 1
    total_ms = (time.perf_counter() - t0) * 1000

    # 6. 汇总结果
    print(f"总耗时: {total_ms:.1f}ms  (keep={kept}, drop={dropped})")

    stages = [
        ("url_exact",        "精确 URL 匹配"),
        ("title_exact",      "精确标题匹配"),
        ("title_similarity", "标题相似度"),
        ("vector_similarity","语义向量"),
    ]
    print(f"\n  {'阶段':<16} {'调用次数':>8} {'总耗时(ms)':>12} {'平均(ms)':>10} {'占比':>8}")
    print(f"  {'-'*56}")
    for key, label in stages:
        timings = deduper._stage_timings[key]
        if not timings:
            continue
        total = sum(timings)
        avg = total / len(timings)
        pct = total / total_ms * 100 if total_ms > 0 else 0
        print(f"  {label:<16} {len(timings):>8} {total:>10.2f} {avg:>10.4f} {pct:>7.1f}%")

    # 7. 清理
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return total_ms


# ─────────────── 主入口 ───────────────

def main():
    parser = argparse.ArgumentParser(description="去重性能基准测试")
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 500, 1000],
                        help="历史记录规模列表 (default: 100 500 1000)")
    parser.add_argument("--items", type=int, default=10,
                        help="每次测试的待去重 item 数 (default: 10)")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="使用 mock 向量（默认启用）")
    parser.add_argument("--real", action="store_false", dest="mock",
                        help="使用真实 embedding API")
    parser.add_argument("--model", type=str, default=None,
                        help="向量模型名（仅在 --real 时有效）")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="输出详细日志")
    args = parser.parse_args()

    llm_client = None
    if not args.mock:
        print("正在初始化 LLM 客户端（真实 API 模式）...")
        config = load_config()
        if args.model:
            config.embedding_model = args.model
        llm_client = LLMClient.from_config(config)
        print(f"  API: {config.embedding_base_url}")
        print(f"  Model: {config.embedding_model}")

    print("去重性能基准测试")
    print(f"历史记录规模: {args.sizes}")
    print(f"每轮测试 items: {args.items}")
    print(f"向量模式: {'Mock' if args.mock else 'Real API'}")

    results = []
    for size in args.sizes:
        total = run_benchmark(
            history_size=size,
            test_items_count=args.items,
            llm_client=llm_client,
            mock=args.mock,
            verbose=args.verbose,
        )
        results.append((size, total))

    print(f"\n{'='*60}")
    print("汇总")
    print(f"{'='*60}")
    print(f"  {'历史记录数':<12} {'总耗时(ms)':<14} {'每 item 平均(ms)':<16}")
    print(f"  {'-'*42}")
    for size, total in results:
        per_item = total / args.items
        print(f"  {size:<12} {total:<14.1f} {per_item:<16.4f}")

    # 估算 N=10000、N=100000 的外推
    if len(args.sizes) >= 2:
        # 简单线性回归：基于最后两个点
        s1, t1 = results[-2]
        s2, t2 = results[-1]
        slope = (t2 - t1) / (s2 - s1)
        intercept = t1 - slope * s1
        print(f"\n  线性外推估算（当前增长速度: {slope:.4f}ms/条）:")
        for est_size in [10000, 50000, 100000]:
            est_time = slope * est_size + intercept
            print(f"    N={est_size:<7} ~ {est_time:.0f}ms ({est_time/args.items:.1f}ms/item)")


if __name__ == "__main__":
    main()
