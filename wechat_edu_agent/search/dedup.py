from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Sequence

from app_constants import PLACEHOLDER_URL_MARKERS
from models.schemas import NewsItem
from utils.file_utils import ensure_dir


@dataclass
class HistoryRecord:
    title: str
    source: str
    url: str
    published_at: str
    searched_at: str
    semantic_text: str
    content_hash: str
    title_key: str
    url_key: str
    vector: list[float] | None = None
    embedding_error: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryRecord":
        vector = data.get("vector")
        if not isinstance(vector, list):
            vector = None
        embedding_error = data.get("embedding_error")
        if embedding_error is not None:
            embedding_error = str(embedding_error)
        return cls(
            title=str(data.get("title", "")),
            source=str(data.get("source", "")),
            url=str(data.get("url", "")),
            published_at=str(data.get("published_at", "")),
            searched_at=str(data.get("searched_at", "")),
            semantic_text=str(data.get("semantic_text", "")),
            content_hash=str(data.get("content_hash", "")),
            title_key=str(data.get("title_key", "")),
            url_key=str(data.get("url_key", "")),
            vector=vector,
            embedding_error=embedding_error,
        )

    def to_dict(self) -> dict:
        payload = {
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at,
            "searched_at": self.searched_at,
            "semantic_text": self.semantic_text,
            "content_hash": self.content_hash,
            "title_key": self.title_key,
            "url_key": self.url_key,
        }
        if self.vector is not None:
            payload["vector"] = self.vector
        if self.embedding_error is not None:
            payload["embedding_error"] = self.embedding_error
        return payload


@dataclass
class DedupDecision:
    title: str
    source: str
    url: str
    duplicate: bool
    reason: str
    matched_title: str = ""
    matched_source: str = ""
    matched_url: str = ""
    similarity: float = 0.0
    title_similarity: float = 0.0
    age_days: int | None = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "duplicate": self.duplicate,
            "reason": self.reason,
            "matched_title": self.matched_title,
            "matched_source": self.matched_source,
            "matched_url": self.matched_url,
            "similarity": self.similarity,
            "title_similarity": self.title_similarity,
            "age_days": self.age_days,
        }


@dataclass
class DedupResult:
    kept_items: list[NewsItem]
    dropped_items: list[DedupDecision]
    history_size: int
    embedding_enabled: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "history_size": self.history_size,
            "embedding_enabled": self.embedding_enabled,
            "warnings": self.warnings,
            "kept_items": [item.model_dump() for item in self.kept_items],
            "dropped_items": [item.to_dict() for item in self.dropped_items],
        }


class SearchHistory:
    def __init__(
        self,
        store_dir: str | Path,
        llm_client=None,
        embedding_model: str | None = None,
        similarity_threshold: float = 0.86,
        title_threshold: float = 0.8,
        recent_days: int = 14,
    ) -> None:
        self.store_dir = Path(store_dir)
        ensure_dir(self.store_dir)
        self.history_path = self.store_dir / "search_history.jsonl"
        self.llm_client = llm_client
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.title_threshold = title_threshold
        self.recent_days = recent_days
        self.records: list[HistoryRecord] = self._load_records()
        self._embedding_warning_emitted = False

    @property
    def embedding_enabled(self) -> bool:
        return bool(self.llm_client and self.embedding_model)

    def filter_items(self, items: Sequence[NewsItem], limit: int | None = None) -> DedupResult:
        warnings: list[str] = []
        kept_items: list[NewsItem] = []
        kept_records: list[HistoryRecord] = []
        dropped_items: list[DedupDecision] = []

        sorted_items = sorted(
            list(items),
            key=lambda item: (item.relevance_score, item.virality_score),
            reverse=True,
        )

        for item in sorted_items:
            if limit is not None and len(kept_items) >= limit:
                break
            decision = self._classify_item(item, kept_records)
            if decision.duplicate:
                dropped_items.append(decision)
                continue
            kept_records.append(self._build_record(item))
            kept_items.append(item)

        if kept_records:
            persisted = self._append_records(kept_records)
            if persisted:
                warnings.append(f"Search history appended with {persisted} item(s).")
        if self._embedding_warning_emitted:
            warnings.append(
                "Semantic deduplication fell back to title/URL matching because embeddings were unavailable."
            )

        return DedupResult(
            kept_items=kept_items,
            dropped_items=dropped_items,
            history_size=len(self.records),
            embedding_enabled=self.embedding_enabled,
            warnings=warnings,
        )

    def is_duplicate(self, news_item: NewsItem) -> bool:
        return self._classify_item(news_item, []).duplicate

    def record_items(self, items: Sequence[NewsItem]) -> int:
        return self._append_records([self._build_record(item) for item in items])

    def _load_records(self) -> list[HistoryRecord]:
        if not self.history_path.exists():
            return []

        records: list[HistoryRecord] = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(HistoryRecord.from_dict(payload))
            except Exception:
                continue
        return records

    def _append_records(self, records: Sequence[HistoryRecord]) -> int:
        ensure_dir(self.history_path.parent)
        if not records:
            return 0

        with self.history_path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

        self.records.extend(records)
        return len(records)

    def _build_record(self, item: NewsItem) -> HistoryRecord:
        semantic_text = self._build_semantic_text(item)
        vector: list[float] = []
        embedding_error: str | None = None
        if self.embedding_enabled:
            vector, embedding_error = self._safe_embed_text(semantic_text)

        return HistoryRecord(
            title=item.title.strip(),
            source=item.source.strip(),
            url=item.url.strip(),
            published_at=item.published_at.strip(),
            searched_at=datetime.now().isoformat(timespec="seconds"),
            semantic_text=semantic_text,
            content_hash=self._hash_text(semantic_text),
            title_key=normalize_title(item.title),
            url_key=normalize_url(item.url),
            vector=vector or None,
            embedding_error=embedding_error,
        )

    def _classify_item(self, item: NewsItem, current_batch: Sequence[HistoryRecord]) -> DedupDecision:
        item_title = item.title.strip()
        item_source = item.source.strip()
        item_url = item.url.strip()
        item_title_key = normalize_title(item_title)
        item_url_key = normalize_url(item_url)
        item_text = self._build_semantic_text(item)
        item_vector, _item_embedding_error = self._safe_embed_text(item_text)

        comparison_records = [*self.records]
        comparison_records.extend(current_batch)

        for record in comparison_records:
            if item_url_key and record.url_key and item_url_key == record.url_key:
                return DedupDecision(
                    title=item_title,
                    source=item_source,
                    url=item_url,
                    duplicate=True,
                    reason="exact url match",
                    matched_title=record.title,
                    matched_source=record.source,
                    matched_url=record.url,
                )

        for record in comparison_records:
            if item_title_key and record.title_key and item_title_key == record.title_key:
                return DedupDecision(
                    title=item_title,
                    source=item_source,
                    url=item_url,
                    duplicate=True,
                    reason="exact title match",
                    matched_title=record.title,
                    matched_source=record.source,
                    matched_url=record.url,
                )

        for record in comparison_records:
            title_similarity = title_similarity_score(item_title, record.title)
            if title_similarity >= self.title_threshold:
                return DedupDecision(
                    title=item_title,
                    source=item_source,
                    url=item_url,
                    duplicate=True,
                    reason="title similarity match",
                    matched_title=record.title,
                    matched_source=record.source,
                    matched_url=record.url,
                    title_similarity=title_similarity,
                )

        if item_vector:
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
                return DedupDecision(
                    title=item_title,
                    source=item_source,
                    url=item_url,
                    duplicate=True,
                    reason="semantic similarity match",
                    matched_title=best_record.title,
                    matched_source=best_record.source,
                    matched_url=best_record.url,
                    similarity=best_score,
                    age_days=self._age_days(best_record.published_at),
                )

        return DedupDecision(
            title=item_title,
            source=item_source,
            url=item_url,
            duplicate=False,
            reason="unique",
        )

    def _safe_embed_text(self, text: str) -> list[float]:
        if not self.embedding_enabled:
            return [], None
        try:
            return self.llm_client.embed_text(text, model=self.embedding_model), None
        except Exception as exc:
            # record the exception message so it is persisted with the history
            self._embedding_warning_emitted = True
            try:
                err = str(exc)
            except Exception:
                err = "embedding_error"
            return [], err

    def _threshold_for_record(self, record: HistoryRecord) -> float:
        age_days = self._age_days(record.published_at)
        base = self.similarity_threshold
        if age_days is None or age_days <= self.recent_days:
            return base

        decay_days = age_days - self.recent_days
        decay = min(0.08, decay_days * 0.002)
        return max(0.78, base - decay)

    @staticmethod
    def _age_days(published_at: str) -> int | None:
        if not published_at:
            return None

        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
            try:
                pub_date = datetime.strptime(published_at, fmt)
                return max(0, (datetime.now() - pub_date).days)
            except ValueError:
                continue
        return None

    @staticmethod
    def _build_semantic_text(item: NewsItem) -> str:
        parts = [
            item.title.strip(),
            item.source.strip(),
            item.published_at.strip(),
            item.summary.strip(),
            " ".join(fact.strip() for fact in item.core_facts if fact.strip()),
            " ".join(point.strip() for point in item.parent_emotion_points if point.strip()),
        ]
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()


def normalize_url(url: str) -> str:
    if not url or url in ("manual://", ""):
        return ""
    cleaned = url.strip().lower()
    if not cleaned or any(marker in cleaned for marker in PLACEHOLDER_URL_MARKERS):
        return ""
    cleaned = re.sub(r"^https?://(www\.)?", "", cleaned)
    return cleaned.rstrip("/")


def normalize_title(title: str) -> str:
    cleaned = re.sub(r"[\s\u3000]+", "", title or "")
    cleaned = re.sub(r"[「」『』\"'《》【】\[\]（）()：:，,。！!？?、·-]", "", cleaned)
    return cleaned[:80]


def title_similarity_score(left: str, right: str) -> float:
    left_clean = normalize_title(left)
    right_clean = normalize_title(right)
    if not left_clean or not right_clean:
        return 0.0

    left_chars = set(left_clean)
    right_chars = set(right_clean)
    char_overlap = len(left_chars & right_chars) / max(1, min(len(left_chars), len(right_chars)))

    left_bigrams = {left_clean[index : index + 2] for index in range(len(left_clean) - 1)}
    right_bigrams = {right_clean[index : index + 2] for index in range(len(right_clean) - 1)}
    bigram_overlap = 0.0
    if left_bigrams and right_bigrams:
        bigram_overlap = len(left_bigrams & right_bigrams) / max(1, min(len(left_bigrams), len(right_bigrams)))

    return max(char_overlap, bigram_overlap)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)