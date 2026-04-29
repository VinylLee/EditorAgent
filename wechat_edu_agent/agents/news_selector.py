from __future__ import annotations

import json
from typing import List, Tuple

from llm.json_schemas import NEWS_SELECT_SCHEMA
from llm.prompts import NEWS_SELECT_PROMPT, SYSTEM_PROMPT
from models.schemas import NewsItem, NewsSelectionResult
from utils.json_utils import safe_json_loads


class NewsSelector:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def select(
        self, candidates: List[NewsItem]
    ) -> Tuple[NewsSelectionResult, List[str]]:
        if len(candidates) == 1:
            return NewsSelectionResult(selected_news=candidates[0]), []

        prompt = NEWS_SELECT_PROMPT + "\n\n候选新闻:\n" + json.dumps(
            [c.model_dump() for c in candidates], ensure_ascii=False, indent=2
        )
        text = self.llm_client.chat_json(
            SYSTEM_PROMPT,
            prompt,
            json_schema=NEWS_SELECT_SCHEMA,
            request_tag="news_select",
        )
        warnings: List[str] = []

        try:
            data = safe_json_loads(text)
            if isinstance(data, dict) and data.get("selected_news"):
                selection = NewsSelectionResult.model_validate(data)
                return selection, warnings
            warnings.append("News selection JSON missing selected_news; fallback used.")
        except Exception as exc:
            warnings.append(f"News selection JSON parse failed; repair attempted. Error: {exc}")

        repaired = self._repair_json(text)
        if repaired:
            try:
                data = safe_json_loads(repaired)
                if isinstance(data, dict) and data.get("selected_news"):
                    selection = NewsSelectionResult.model_validate(data)
                    return selection, warnings
            except Exception as exc:
                warnings.append(
                    f"News selection JSON repair failed; fallback used. Error: {exc}"
                )

        return NewsSelectionResult(selected_news=candidates[0]), warnings

    def _repair_json(self, raw_text: str) -> str:
        prompt = (
            "你是 JSON 修复工具。\n"
            "请将以下内容修复为符合指定结构的 JSON，仅输出 JSON。\n\n"
            "结构要求:\n"
            "{\n"
            "  \"selected_news\": {\n"
            "    \"news_type\": \"\",\n"
            "    \"title\": \"\",\n"
            "    \"source\": \"\",\n"
            "    \"published_at\": \"\",\n"
            "    \"url\": \"\",\n"
            "    \"summary\": \"\",\n"
            "    \"core_facts\": [],\n"
            "    \"parent_emotion_points\": [],\n"
            "    \"relevance_score\": 0,\n"
            "    \"virality_score\": 0,\n"
            "    \"reason\": \"\"\n"
            "  },\n"
            "  \"reason\": \"\",\n"
            "  \"parent_emotion_points\": [],\n"
            "  \"deep_logic_angles\": [],\n"
            "  \"suggested_article_angle\": \"\",\n"
            "  \"risk_notes\": []\n"
            "}\n\n"
            "待修复内容:\n"
            + (raw_text or "")
        )
        return self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="news_select_repair",
            temperature=0.1,
        ).strip()
