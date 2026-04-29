from __future__ import annotations

import json
from typing import List, Tuple

from llm.prompts import FINAL_POLISH_PROMPT, SYSTEM_PROMPT
from models.schemas import FactExtractResult


class PolishAgent:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def polish(
        self,
        final_title: str,
        article_markdown: str,
        fact_extract: FactExtractResult,
    ) -> Tuple[str, List[str]]:
        fact_json = json.dumps(fact_extract.model_dump(), ensure_ascii=False, indent=2)
        prompt = (
            FINAL_POLISH_PROMPT
            + "\n\n指定标题:\n"
            + final_title
            + "\n\n事实抽取结果:\n"
            + fact_json
            + "\n\n待润色文章:\n"
            + (article_markdown or "")
        )
        text = self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="final_polish",
            temperature=0.2,
        ).strip()
        warnings: List[str] = []
        if not text:
            warnings.append("Final polish returned empty content; fallback used.")
            return article_markdown, warnings
        return text, warnings
