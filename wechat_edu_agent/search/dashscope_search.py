"""DashScope search provider using native DashScope protocol with enable_source=True.

Uses DashScope's native SDK to enable web search and retrieve source URLs directly.
No need for DuckDuckGo fallback when enable_source is properly configured.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import List, Dict, Any

import dashscope
from dashscope import Generation
from dashscope.api_entities.dashscope_response import GenerationResponse

from app_constants import DASHSCOPE_SEARCH_MODEL, PLACEHOLDER_URL_MARKERS
from models.schemas import NewsItem, SearchResult
from search.base import SearchProvider
from llm.prompts import SEARCH_SYSTEM_PROMPT


class DashScopeSearchProvider(SearchProvider):
    """Search provider using DashScope native protocol with web search and source URLs."""

    def __init__(
        self, api_key: str, model: str | None = None, enable_url_lookup: bool = True
    ) -> None:
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is required for DashScope search")

        # Initialize DashScope SDK once; request-time behavior remains unchanged.
        dashscope.api_key = api_key
        self.api_key = api_key
        self.model = model or DASHSCOPE_SEARCH_MODEL
        # Keep URL lookup fallback for cases where provider omits URLs.
        self.enable_url_lookup = enable_url_lookup

    def search(self, topic: str, news_type: str, limit: int = 5) -> SearchResult:
        user_prompt = self._build_search_prompt(topic, news_type, limit)

        try:
            # 🔑 使用 DashScope 原生 SDK 调用，启用 enable_source
            response: GenerationResponse = Generation.call(
                model=self.model,
                messages=[
                    {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                result_format="message",  # 🔑 必须设置为 message 格式
                enable_search=True,       # 🔑 启用联网搜索
                search_options={
                    "enable_source": True,      # 🔑 核心：返回搜索来源（含URL）
                    "enable_citation": True,    # 在正文中添加角标标注 [ref_1]
                    "citation_format": "[ref_<number>]",
                    "forced_search": True,      # 强制执行搜索，避免模型跳过
                },
            )
            
            # 检查响应状态
            if response.status_code != 200:
                raise RuntimeError(f"DashScope API error: {response.code} - {response.message}")
            
            # 提取模型回答
            raw_text = response.output.choices[0].message.content or ""
            
            # 🔑 提取搜索来源信息（含URL）- 兼容 SDK 在不同版本的返回结构
            search_sources = self._extract_search_sources(response)
            
        except Exception as exc:
            raise RuntimeError(f"DashScope search failed: {exc}") from exc

        if not raw_text.strip():
            raise RuntimeError("DashScope search returned empty content")

        # 🔑 解析新闻项时传入 search_sources 映射
        items = self._parse_news_items(raw_text, news_type, search_sources)
        if not items:
            items = self._fallback_single_item(raw_text, news_type, search_sources)

        # 原生协议已返回URL，DuckDuckGo 回退通常不需要，但保留作为双重保障
        if self.enable_url_lookup:
            missing = sum(1 for it in items if not self._is_real_url(it.url))
            if missing > 0:
                self._lookup_urls(items)

        return SearchResult(items=items, raw_text=raw_text, provider="dashscope")

    @staticmethod
    def _extract_search_sources(response: GenerationResponse) -> Dict[int, Dict[str, str]]:
        """Extract source map from DashScope response across object/dict/list variants."""
        search_sources: Dict[int, Dict[str, str]] = {}
        output = getattr(response, "output", None)
        if output is None:
            return search_sources

        search_info = getattr(output, "search_info", None)
        if not search_info and isinstance(output, dict):
            search_info = output.get("search_info")
        if not search_info:
            return search_sources

        if isinstance(search_info, dict):
            results = search_info.get("search_results") or search_info.get("results") or []
        else:
            results = getattr(search_info, "search_results", None) or getattr(search_info, "results", None) or []

        for pos, src in enumerate(results, start=1):
            if isinstance(src, dict):
                idx = src.get("index") or src.get("ref_index") or pos
                url = src.get("url", "")
                title = src.get("title", "")
                site_name = src.get("siteName") or src.get("site_name", "")
                icon = src.get("icon", "")
            else:
                idx = getattr(src, "index", None) or getattr(src, "ref_index", None) or pos
                url = getattr(src, "url", "")
                title = getattr(src, "title", "")
                site_name = getattr(src, "siteName", "") or getattr(src, "site_name", "")
                icon = getattr(src, "icon", "")

            try:
                idx_int = int(idx)
            except (TypeError, ValueError):
                idx_int = pos

            search_sources[idx_int] = {
                "url": url or "",
                "title": title or "",
                "siteName": site_name or "",
                "icon": icon or "",
            }

        return search_sources

    def _build_search_prompt(self, topic: str, news_type: str, limit: int) -> str:
        """构建搜索提示词，要求模型返回带 ref_index 的结构化格式"""
        type_hint = {
            "教育部政策": "教育部发布的最新政策、通知、文件",
            "学校案例": "各地学校的具体做法、改革案例、典型事件",
            "社会事件": "与教育相关的社会热点、争议事件、媒体报道",
        }.get(news_type, "教育相关新闻")

        return (
            f"请搜索关于「{topic}」的近期教育新闻。\n"
            f"新闻类型偏好：{type_hint}。\n"
            f"最多返回 {limit} 条最相关的新闻。\n"
            f"请确保返回完整的新闻正文内容，不要只给摘要。\n"
            f"请严格按以下格式返回每条新闻（ref_index 对应搜索来源的角标数字）：\n"
            f"---news-item---\n"
            f"---meta---\n"
            f'{{"title": "标题", "source": "来源", "date": "YYYY-MM-DD", "url": "URL", "ref_index": 1}}\n'
            f"---body---\n"
            f"新闻正文内容...\n"
            f"---end---"
        )

    def _parse_news_items(self, raw_text: str, news_type: str, 
                         search_sources: Dict[int, Dict[str, str]]) -> List[NewsItem]:
        """解析新闻项，优先从 search_sources 填充 URL"""
        items: List[NewsItem] = []
        blocks = re.split(r"---news-item---", raw_text)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            meta_match = re.search(r"---meta---\s*(.*?)\s*---body---", block, re.DOTALL)
            if not meta_match:
                continue

            meta_json_str = meta_match.group(1).strip()
            body = block[meta_match.end():].strip()
            body = re.sub(r"---end---\s*$", "", body).strip()

            try:
                meta = json.loads(meta_json_str)
            except json.JSONDecodeError:
                continue

            title = meta.get("title", "未命名新闻")
            source = meta.get("source", "网络来源")
            published_at = meta.get("date", "未知")
            url = meta.get("url", "")
            ref_index = meta.get("ref_index")  # 🔑 获取模型返回的角标索引

            # 🔑 优先级1: 从 search_sources 中获取URL（最可靠）
            if (not url or self._is_placeholder_url(url)) and ref_index and ref_index in search_sources:
                src_info = search_sources[ref_index]
                url = src_info.get("url", "")
                if not source or source in ("未知来源", "网络来源"):
                    source = src_info.get("siteName", source)

            # 优先级2: 从正文中提取URL（兜底）
            if not url or self._is_placeholder_url(url):
                url = self._extract_url_from_text(body)

            if self._is_placeholder_url(url):
                url = ""
            
            # 提取域名作为来源名称
            if (not source or source in ("未知来源", "网络来源")) and url:
                source = self._extract_domain(url)

            summary = body[:300].strip()
            core_facts = self._extract_sentences(body, min_count=3)

            item = NewsItem(
                news_type=news_type,
                title=title,
                source=source,
                published_at=published_at,
                url=url,  # 🔑 此时 url 应已填充
                summary=summary,
                core_facts=core_facts,
                parent_emotion_points=["教育焦虑", "升学压力"],
                relevance_score=70,
                virality_score=65,
                reason=f"DashScope搜索: {title}",
            )
            items.append(item)

        return items

    def _fallback_single_item(self, raw_text: str, news_type: str,
                           search_sources: Dict[int, Dict[str, str]]) -> List[NewsItem]:
        """兜底解析：当结构化解析失败时使用"""
        title = self._infer_title(raw_text)
        summary = raw_text[:300].strip()
        core_facts = self._extract_sentences(raw_text, min_count=2)
        
        # 🔑 尝试从 search_sources 获取第一个URL作为fallback
        url = ""
        source = "DashScope搜索"
        if search_sources:
            first_src = next(iter(search_sources.values()), None)
            if first_src:
                url = first_src.get("url", "")
                source = first_src.get("siteName", "DashScope搜索")

        if self._is_placeholder_url(url):
            url = ""

        return [
            NewsItem(
                news_type=news_type,
                title=title,
                source=source,
                published_at=datetime.now().strftime("%Y-%m-%d"),
                url=url,
                summary=summary,
                core_facts=core_facts,
                parent_emotion_points=["教育焦虑"],
                relevance_score=60,
                virality_score=55,
                reason="DashScope搜索（自动解析）",
            )
        ]

    # ==================== 以下辅助方法保持不变 ====================
    
    @staticmethod
    def _infer_title(text: str) -> str:
        first_line = text.splitlines()[0].strip()
        if 8 <= len(first_line) <= 80:
            return first_line
        return "搜索新闻结果"

    @staticmethod
    def _extract_sentences(text: str, min_count: int = 2) -> List[str]:
        sentences = re.split(r"[。！？!?\\n]", text)
        facts = [s.strip() for s in sentences if len(s.strip()) > 10]
        return facts[:max(min_count, 3)] if facts else ["新闻内容待核实"]

    @staticmethod
    def _extract_url_from_text(text: str) -> str:
        """Try to find a real news URL in the body text."""
        url_pattern = re.compile(r"https?://[^\s\)）\]】\u4e00-\u9fff]+")
        matches = url_pattern.findall(text)
        for url in matches:
            url = url.rstrip(".,;:!?")
            if len(url) > 20 and not any(
                d in url.lower() for d in PLACEHOLDER_URL_MARKERS
            ):
                return url
        return ""

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract a readable domain name from a URL."""
        match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if match:
            domain = match.group(1)
            parts = domain.split(".")
            if len(parts) >= 2:
                return parts[-2] if parts[-2] not in ("com", "net", "org", "cn") else parts[-3] if len(parts) >= 3 else domain
            return domain
        return "网络来源"

    @staticmethod
    def _is_real_url(url: str) -> bool:
        return bool(url) and url not in ("", "无提供", "无", "暂无", "manual://") and not any(
            p in url for p in PLACEHOLDER_URL_MARKERS
        )

    @staticmethod
    def _is_placeholder_url(url: str) -> bool:
        if not url:
            return True
        lowered = url.lower()
        return any(marker in lowered for marker in PLACEHOLDER_URL_MARKERS)

    def _lookup_urls(self, items: List[NewsItem]) -> None:
        """Use DuckDuckGo Lite as fallback for missing URLs (rarely needed with enable_source)."""
        import urllib.parse
        import urllib.request
        
        for item in items:
            if self._is_real_url(item.url):
                continue
            found_url = self._search_duckduckgo(item.title)
            if found_url:
                item.url = found_url
                if not item.source or item.source in ("未知来源", "网络来源"):
                    item.source = self._extract_domain(found_url)

    @staticmethod
    def _search_duckduckgo(query: str) -> str:
        """Search DuckDuckGo Lite and return the first non-DDG result URL."""
        import urllib.parse
        import urllib.request
        
        encoded = urllib.parse.quote(query)
        ddg_url = f"https://lite.duckduckgo.com/lite/?q={encoded}"

        try:
            req = urllib.request.Request(
                ddg_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:120.0) Gecko/20100101 Firefox/120.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

        for pat in [
            re.compile(r'<a[^>]*class="result-link"[^>]*href="(https?://[^"]+)"'),
            re.compile(r'<a[^>]*href="(https?://[^"]+)"[^>]*class="result-link"'),
        ]:
            match = pat.search(html)
            if match:
                url = match.group(1)
                if "duckduckgo.com" not in url:
                    return url

        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            url = m.group(1)
            if "duckduckgo.com" not in url and len(url) > 25:
                return url

        return ""