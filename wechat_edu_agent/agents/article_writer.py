from __future__ import annotations

import json
from typing import List, Tuple

from app_constants import DEFAULT_LONG_FORM_MAX_TOKENS
from llm.prompts import ARTICLE_WRITE_PROMPT, SYSTEM_PROMPT
from models.schemas import FactExtractResult, NewsItem
from utils.text_utils import clean_llm_article


class ArticleWriter:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    @staticmethod
    def _format_source_list(news_items: List[NewsItem]) -> str:
        valid = [
            item for item in news_items
            if item.source and item.source.strip()
            and item.source.strip() not in ("用户提供", "网络来源", "未知来源")
        ]
        if not valid:
            return ""
        lines = ["\n\n可参考的新闻来源列表（请在正文中标注来源媒体名称，并在文末用Markdown格式列出「参考来源」章节，包含来源媒体名称和URL）："]
        for i, item in enumerate(valid, start=1):
            source = item.source.strip()
            title = item.title.strip()
            url = item.url.strip() if item.url else "（无URL）"
            lines.append(f"{i}. {source} | {url} | 标题：{title}")
        return "\n".join(lines)

    def write(
        self,
        news: NewsItem,
        raw_text: str,
        fact_extract: FactExtractResult,
        article_angle: str,
        source_list: List[NewsItem] | None = None,
    ) -> Tuple[str, List[str]]:
        news_json = json.dumps(news.model_dump(), ensure_ascii=False, indent=2)
        fact_json = json.dumps(fact_extract.model_dump(), ensure_ascii=False, indent=2)
        source_block = self._format_source_list(source_list or [])
        prompt = (
            ARTICLE_WRITE_PROMPT
            + "\n\n新闻信息:\n"
            + news_json
            + "\n\n事实抽取结果（唯一事实来源）:\n"
            + fact_json
            + "\n\n文章角度:\n"
            + (article_angle or "")
            + source_block
        )
        article = self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="article_write",
            max_tokens=DEFAULT_LONG_FORM_MAX_TOKENS,
        ).strip()
        article = clean_llm_article(article)
        warnings: List[str] = []
        if not article:
            warnings.append("Article generation returned empty content.")
        elif getattr(self.llm_client, "last_finish_reason", None) == "length":
            warnings.append("Article generation was truncated by token limit.")
        return article, warnings
