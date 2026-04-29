from __future__ import annotations

import re
from pathlib import Path
from typing import List

from models.schemas import NewsItem, SearchResult
from search.base import SearchProvider


class ManualNewsProvider(SearchProvider):
    def __init__(self, manual_news_path: Path, news_type: str = "社会事件") -> None:
        self.manual_news_path = Path(manual_news_path)
        self.news_type = news_type

    def search(self, topic: str, news_type: str, limit: int = 5) -> SearchResult:
        raw_text = self.manual_news_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            raise ValueError("Manual news file is empty.")

        title = self._infer_title(raw_text)
        summary = raw_text[:300].strip()
        core_facts = self._extract_core_facts(raw_text)

        item = NewsItem(
            news_type=news_type or self.news_type,
            title=title,
            source="用户提供",
            published_at="未知",
            url="manual://",
            summary=summary,
            core_facts=core_facts,
            parent_emotion_points=["担心孩子被甩开", "担心政策变化影响规划"],
            relevance_score=60,
            virality_score=60,
            reason="用户手动提供新闻",
        )
        return SearchResult(items=[item], raw_text=raw_text, provider="manual")

    def _infer_title(self, text: str) -> str:
        first_line = text.splitlines()[0].strip()
        if 8 <= len(first_line) <= 60:
            return first_line
        return "用户提供新闻"

    def _extract_core_facts(self, text: str) -> List[str]:
        sentences = re.split(r"[。！？!?]", text)
        facts = [s.strip() for s in sentences if len(s.strip()) > 6]
        return facts[:3] if facts else ["新闻事实需人工核对"]
