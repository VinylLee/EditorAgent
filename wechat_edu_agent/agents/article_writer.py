from __future__ import annotations

import json
from typing import List, Tuple

from llm.prompts import ARTICLE_WRITE_PROMPT, SYSTEM_PROMPT
from models.schemas import FactExtractResult, NewsItem


class ArticleWriter:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def write(
        self,
        news: NewsItem,
        raw_text: str,
        fact_extract: FactExtractResult,
        article_angle: str,
    ) -> Tuple[str, List[str]]:
        news_json = json.dumps(news.model_dump(), ensure_ascii=False, indent=2)
        fact_json = json.dumps(fact_extract.model_dump(), ensure_ascii=False, indent=2)
        prompt = (
            ARTICLE_WRITE_PROMPT
            + "\n\n新闻信息:\n"
            + news_json
            + "\n\n事实抽取结果:\n"
            + fact_json
            + "\n\n文章角度:\n"
            + (article_angle or "")
            + "\n\n新闻素材:\n"
            + (raw_text or "")
        )
        article = self.llm_client.chat_text(
            SYSTEM_PROMPT, prompt, request_tag="article_write"
        ).strip()
        warnings: List[str] = []
        if not article:
            warnings.append("Article generation returned empty content.")
        return article, warnings
