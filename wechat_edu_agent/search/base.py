from __future__ import annotations

from abc import ABC, abstractmethod

from models.schemas import SearchResult


class SearchProvider(ABC):
    @abstractmethod
    def search(self, topic: str, news_type: str, limit: int = 5) -> SearchResult:
        raise NotImplementedError
