"""Multi-source search aggregator with dedup, scoring, and fallback.

Combines results from multiple SearchProviders, deduplicates by URL/title,
sorts by relevance, and filters stale news.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List

from app_constants import PLACEHOLDER_URL_MARKERS
from models.schemas import NewsItem, SearchResult
from search.base import SearchProvider


class SearchAggregator:
    """Aggregates search results from multiple providers with fallback chain."""

    def __init__(
        self,
        providers: List[SearchProvider],
        max_age_days: int = 30,
    ) -> None:
        if not providers:
            raise ValueError("At least one provider is required")
        self.providers = providers
        self.max_age_days = max_age_days

    def search(self, topic: str, news_type: str, limit: int = 5) -> SearchResult:
        errors: List[str] = []
        all_items: List[NewsItem] = []
        raw_texts: List[str] = []

        for provider in self.providers:
            provider_name = provider.__class__.__name__
            try:
                result = provider.search(topic=topic, news_type=news_type, limit=limit)
                if result.items:
                    all_items.extend(result.items)
                    raw_texts.append(result.raw_text)
            except Exception as exc:
                errors.append(f"{provider_name}: {exc}")
                continue

        if not all_items:
            raise RuntimeError(
                f"All search providers failed. Errors: {'; '.join(errors)}"
            )

        if errors:
            raw_texts.insert(0, f"搜索警告: {'; '.join(errors)}")

        merged_items = self._merge_and_dedup(all_items, limit)
        merged_text = "\n\n---\n\n".join(raw_texts)

        return SearchResult(
            items=merged_items,
            raw_text=merged_text,
            provider="auto",
        )

    def _merge_and_dedup(self, items: List[NewsItem], limit: int) -> List[NewsItem]:
        # Sort by relevance score descending, then virality
        sorted_items = sorted(
            items,
            key=lambda x: (x.relevance_score, x.virality_score),
            reverse=True,
        )

        # Phase 1: enrich missing URLs by cross-referencing across providers
        self._enrich_urls_from_peers(sorted_items)

        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        unique: List[NewsItem] = []

        for item in sorted_items:
            if len(unique) >= limit:
                break
            if self._is_stale(item):
                continue

            url_key = self._normalize_url(item.url)
            title_key = self._normalize_title(item.title)

            # Only deduplicate by URL if it's a real URL (not a placeholder)
            if url_key and url_key in seen_urls and self._has_real_url(item.url):
                continue
            if title_key in seen_titles:
                continue

            if url_key and self._has_real_url(item.url):
                seen_urls.add(url_key)
            seen_titles.add(title_key)
            unique.append(item)

        return unique

    def _enrich_urls_from_peers(self, items: List[NewsItem]) -> None:
        """Cross-reference: for items without real URLs, borrow URLs from
        similar-titled items that have them (e.g., DashScope content + Tavily URL)."""
        # Build lookups
        items_with_url: list[NewsItem] = [
            it for it in items if self._has_real_url(it.url)
        ]
        items_without_url: list[NewsItem] = [
            it for it in items if not self._has_real_url(it.url)
        ]

        if not items_with_url or not items_without_url:
            return

        for needy in items_without_url:
            for donor in items_with_url:
                if self._titles_match(needy.title, donor.title):
                    needy.url = donor.url
                    if (not needy.source or needy.source in (
                        "未知来源", "网络来源", "DashScope搜索"
                    )) and donor.source not in (
                        "未知来源", "网络来源", "用户提供", "DashScope搜索"
                    ):
                        needy.source = donor.source
                    break

    @staticmethod
    def _has_real_url(url: str) -> bool:
        return bool(url) and url not in ("", "无提供", "无", "暂无", "manual://") and not any(
            p in url.lower() for p in PLACEHOLDER_URL_MARKERS
        )

    @staticmethod
    def _titles_match(a: str, b: str) -> bool:
        """Check if two news titles likely refer to the same story.
        Uses combined character-level + bigram overlap for Chinese text."""
        def clean(s: str) -> str:
            return re.sub(r"[「」""''《》【】\s：:，,。！!？?？]" , "", s)

        a_clean = clean(a)
        b_clean = clean(b)
        if not a_clean or not b_clean:
            return False

        # Character-level overlap
        a_chars = set(a_clean)
        b_chars = set(b_clean)
        char_overlap = len(a_chars & b_chars) / min(len(a_chars), len(b_chars))

        # Bigram overlap
        def bigrams(s: str) -> set[str]:
            return {s[i:i+2] for i in range(len(s) - 1)}
        a_bi = bigrams(a_clean)
        b_bi = bigrams(b_clean)
        bi_overlap = len(a_bi & b_bi) / min(len(a_bi), len(b_bi)) if a_bi and b_bi else 0

        return char_overlap > 0.45 or bi_overlap > 0.2

    def _is_stale(self, item: NewsItem) -> bool:
        date_str = item.published_at
        if not date_str or date_str == "未知":
            return False

        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]:
            try:
                pub_date = datetime.strptime(date_str, fmt)
                if datetime.now() - pub_date > timedelta(days=self.max_age_days):
                    return True
                return False
            except ValueError:
                continue
        return False

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url or url in ("manual://", ""):
            return ""
        return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")

    @staticmethod
    def _normalize_title(title: str) -> str:
        return re.sub(r"\s+", "", title)[:50]
