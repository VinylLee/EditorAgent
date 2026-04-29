"""DashScope search provider using enable_search=True.

Uses DashScope's OpenAI-compatible API with web search enabled.
The model searches the web and returns synthesized news content.

DashScope does NOT return source URLs in its response. To fill in missing
URLs, this provider can optionally query DuckDuckGo Lite (free, no API key)
to look up article links by title.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import List

from openai import OpenAI

from models.schemas import NewsItem, SearchResult
from search.base import SearchProvider

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_SEARCH_MODEL = "qwen-max"

SEARCH_SYSTEM_PROMPT = """你是一个教育新闻搜索助手。请搜索与中国教育政策、减负、高考、教育内卷相关的近期新闻。

要求：
1. 搜索最近30天内的新闻
2. 返回完整的新据报道内容，包括标题、来源、发布日期、URL和正文
3. 优先选择具有话题性和争议性的新闻
4. 每则新闻用 "---news-item---" 分隔
5. 每则新闻内部用 "---meta---" 分隔元数据和正文
6. 元数据部分使用 JSON 格式

输出格式示例：
---news-item---
---meta---
{"title": "新闻标题", "source": "新闻来源", "date": "2026-04-20", "url": "https://..."}
---body---
新闻正文内容...
---end---

请确保返回至少1条、最多5条新闻。"""


class DashScopeSearchProvider(SearchProvider):
    """Search provider using DashScope (Alibaba Cloud) with web search enabled."""

    def __init__(
        self, api_key: str, model: str | None = None, enable_url_lookup: bool = True
    ) -> None:
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is required for DashScope search")
        self.api_key = api_key
        self.model = model or DASHSCOPE_SEARCH_MODEL
        self.enable_url_lookup = enable_url_lookup
        self.client = OpenAI(
            base_url=DASHSCOPE_BASE_URL,
            api_key=api_key,
        )

    def search(self, topic: str, news_type: str, limit: int = 5) -> SearchResult:
        user_prompt = self._build_search_prompt(topic, news_type, limit)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
                extra_body={"enable_search": True},
            )
            raw_text = response.choices[0].message.content or ""
        except Exception as exc:
            raise RuntimeError(f"DashScope search failed: {exc}") from exc

        if not raw_text.strip():
            raise RuntimeError("DashScope search returned empty content")

        items = self._parse_news_items(raw_text, news_type)
        if not items:
            items = self._fallback_single_item(raw_text, news_type)

        # Fill in missing URLs via free DuckDuckGo lookup
        if self.enable_url_lookup:
            missing = sum(1 for it in items if not self._is_real_url(it.url))
            if missing:
                self._lookup_urls(items)

        return SearchResult(items=items, raw_text=raw_text, provider="dashscope")

    def _build_search_prompt(self, topic: str, news_type: str, limit: int) -> str:
        type_hint = {
            "教育部政策": "教育部发布的最新政策、通知、文件",
            "学校案例": "各地学校的具体做法、改革案例、典型事件",
            "社会事件": "与教育相关的社会热点、争议事件、媒体报道",
        }.get(news_type, "教育相关新闻")

        return (
            f"请搜索关于「{topic}」的近期教育新闻。\n"
            f"新闻类型偏好：{type_hint}。\n"
            f"最多返回 {limit} 条最相关的新闻。\n"
            f"请确保返回完整的新闻正文内容，不要只给摘要。"
        )

    def _parse_news_items(self, raw_text: str, news_type: str) -> List[NewsItem]:
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

            # Fallback: extract URL from body text if meta didn't provide one
            if not url or url in ("无提供", "无", "暂无"):
                url = self._extract_url_from_text(body)
            if (not source or source in ("未知来源", "网络来源")) and url:
                source = self._extract_domain(url)

            summary = body[:300].strip()
            core_facts = self._extract_sentences(body, min_count=3)

            item = NewsItem(
                news_type=news_type,
                title=title,
                source=source,
                published_at=published_at,
                url=url,
                summary=summary,
                core_facts=core_facts,
                parent_emotion_points=["教育焦虑", "升学压力"],
                relevance_score=70,
                virality_score=65,
                reason=f"DashScope搜索: {title}",
            )
            items.append(item)

        return items

    def _fallback_single_item(self, raw_text: str, news_type: str) -> List[NewsItem]:
        title = self._infer_title(raw_text)
        summary = raw_text[:300].strip()
        core_facts = self._extract_sentences(raw_text, min_count=2)

        return [
            NewsItem(
                news_type=news_type,
                title=title,
                source="DashScope搜索",
                published_at=datetime.now().strftime("%Y-%m-%d"),
                url="",
                summary=summary,
                core_facts=core_facts,
                parent_emotion_points=["教育焦虑"],
                relevance_score=60,
                virality_score=55,
                reason="DashScope搜索（自动解析）",
            )
        ]

    @staticmethod
    def _infer_title(text: str) -> str:
        first_line = text.splitlines()[0].strip()
        if 8 <= len(first_line) <= 80:
            return first_line
        return "搜索新闻结果"

    @staticmethod
    def _extract_sentences(text: str, min_count: int = 2) -> List[str]:
        sentences = re.split(r"[。！？!?\n]", text)
        facts = [s.strip() for s in sentences if len(s.strip()) > 10]
        return facts[:max(min_count, 3)] if facts else ["新闻内容待核实"]

    @staticmethod
    def _extract_url_from_text(text: str) -> str:
        """Try to find a real news URL in the body text."""
        url_pattern = re.compile(r"https?://[^\s\)）\]】一-鿿]+")
        matches = url_pattern.findall(text)
        for url in matches:
            url = url.rstrip(".,;:!?")
            if len(url) > 20 and not any(
                d in url for d in ("example.com", "test.com", "localhost")
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
        return bool(url) and url not in ("", "无提供", "无", "暂无", "manual://")

    def _lookup_urls(self, items: List[NewsItem]) -> None:
        """Use DuckDuckGo Lite (free, no API key) to find URLs for items that lack them."""
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
        """Search DuckDuckGo Lite and return the first non-DDG result URL.
        Uses only stdlib (urllib), no extra dependencies or API keys."""
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

        # DuckDuckGo Lite: result links have class="result-link"
        for pat in [
            re.compile(r'<a[^>]*class="result-link"[^>]*href="(https?://[^"]+)"'),
            re.compile(r'<a[^>]*href="(https?://[^"]+)"[^>]*class="result-link"'),
        ]:
            match = pat.search(html)
            if match:
                url = match.group(1)
                if "duckduckgo.com" not in url:
                    return url

        # Fallback: grab first plausible external link
        for m in re.finditer(r'href="(https?://[^"]+)"', html):
            url = m.group(1)
            if "duckduckgo.com" not in url and len(url) > 25:
                return url

        return ""
