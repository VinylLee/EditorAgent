"""Tavily search provider.

Uses the Tavily Search API to find news articles and fetch their content.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List

from app_constants import TAVILY_API_URL
from models.schemas import NewsItem, SearchResult
from search.base import SearchProvider


class TavilySearchProvider(SearchProvider):
    """Search provider using Tavily Search API."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("TAVILY_API_KEY is required for Tavily search")
        self.api_key = api_key

    def search(self, topic: str, news_type: str, limit: int = 5) -> SearchResult:
        import requests  # lazy import — only needed when tavily is used

        query = self._build_query(topic, news_type)

        try:
            response = requests.post(
                TAVILY_API_URL,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": min(limit, 10),
                    "include_answer": True,
                    "include_raw_content": False,
                    "include_domains": [],
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"Tavily search request failed: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Tavily response parse failed: {exc}") from exc

        items = self._parse_results(data, news_type)
        if not items:
            raise RuntimeError("Tavily search returned no usable results")

        raw_text = self._build_raw_text(data, items)
        return SearchResult(items=items, raw_text=raw_text, provider="tavily")

    def _build_query(self, topic: str, news_type: str) -> str:
        type_keywords = {
            "教育部政策": "教育部 政策 通知",
            "学校案例": "学校 改革 案例",
            "社会事件": "教育 热点 争议",
        }.get(news_type, "教育 新闻")

        return f"{topic} {type_keywords} 最新"

    def _parse_results(self, data: dict, news_type: str) -> List[NewsItem]:
        results = data.get("results", [])
        items: List[NewsItem] = []

        for r in results:
            title = r.get("title", "未命名")
            url = r.get("url", "")
            content = r.get("content", "")
            score = r.get("score", 0.5)

            title_clean = re.sub(r"\s+", " ", title).strip()
            content_clean = re.sub(r"\s+", " ", content).strip()

            core_facts = self._extract_sentences(content_clean)
            relevance = min(95, int(score * 100))

            item = NewsItem(
                news_type=news_type,
                title=title_clean,
                source=self._extract_source(url),
                published_at=self._guess_date(content_clean),
                url=url,
                summary=content_clean[:300],
                core_facts=core_facts,
                parent_emotion_points=["教育焦虑", "升学压力"],
                relevance_score=relevance,
                virality_score=min(90, relevance + 5),
                reason=f"Tavily搜索: relevance={relevance}",
            )
            items.append(item)

        return items

    def _build_raw_text(self, data: dict, items: List[NewsItem]) -> str:
        parts: List[str] = []

        answer = data.get("answer", "")
        if answer:
            parts.append(answer)

        for item in items:
            parts.append(f"标题：{item.title}")
            parts.append(f"来源：{item.source}")
            parts.append(f"日期：{item.published_at}")
            parts.append(f"URL：{item.url}")
            parts.append(item.summary)
            parts.append("")

        return "\n".join(parts).strip()

    @staticmethod
    def _extract_source(url: str) -> str:
        if not url:
            return "网络来源"
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or ""
            host = re.sub(r"^www\.", "", host)
            return host if host else "网络来源"
        except Exception:
            return "网络来源"

    @staticmethod
    def _guess_date(text: str) -> str:
        patterns = [
            r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
            r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                y, mo, d = m.groups()
                return f"{y}-{int(mo):02d}-{int(d):02d}"
        return "未知"

    @staticmethod
    def _extract_sentences(text: str) -> List[str]:
        sentences = re.split(r"[。！？!?\n]", text)
        facts = [s.strip() for s in sentences if len(s.strip()) > 10]
        return facts[:3] if facts else ["新闻内容待核实"]
