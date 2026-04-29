from __future__ import annotations

import json
from typing import List, Tuple

from llm.json_schemas import TITLE_GEN_SCHEMA, TITLE_SELECT_SCHEMA
from llm.prompts import SYSTEM_PROMPT, TITLE_GEN_PROMPT, TITLE_SELECT_PROMPT
from models.schemas import TitleCandidate, TitleSelection
from utils.json_utils import safe_json_loads


class TitleOptimizer:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def generate_titles(self, article: str) -> Tuple[List[TitleCandidate], List[str]]:
        prompt = TITLE_GEN_PROMPT + "\n\n文章内容:\n" + article
        text = self.llm_client.chat_json(
            SYSTEM_PROMPT,
            prompt,
            json_schema=TITLE_GEN_SCHEMA,
            request_tag="title_generate",
        )
        warnings: List[str] = []

        try:
            data = safe_json_loads(text)
            items = None
            if isinstance(data, dict):
                items = data.get("titles")
            elif isinstance(data, list):
                items = data
            if isinstance(items, list):
                titles = [TitleCandidate.model_validate(item) for item in items]
                if titles:
                    return titles, warnings
            warnings.append("Title JSON missing titles list; fallback titles used.")
        except Exception as exc:
            warnings.append(f"Title JSON parse failed; repair attempted. Error: {exc}")

        repaired = self._repair_title_gen(text)
        if repaired:
            try:
                data = safe_json_loads(repaired)
                items = None
                if isinstance(data, dict):
                    items = data.get("titles")
                elif isinstance(data, list):
                    items = data
                if isinstance(items, list):
                    titles = [TitleCandidate.model_validate(item) for item in items]
                    if titles:
                        return titles, warnings
            except Exception as exc:
                warnings.append(
                    f"Title JSON repair failed; fallback titles used. Error: {exc}"
                )

        return self._fallback_titles(), warnings

    def select_title(
        self, titles: List[TitleCandidate], article: str
    ) -> Tuple[TitleSelection, List[str]]:
        prompt = TITLE_SELECT_PROMPT + "\n\n候选标题:\n" + json.dumps(
            [t.model_dump() for t in titles], ensure_ascii=False, indent=2
        )
        prompt += "\n\n文章内容:\n" + article
        text = self.llm_client.chat_json(
            SYSTEM_PROMPT,
            prompt,
            json_schema=TITLE_SELECT_SCHEMA,
            request_tag="title_select",
        )
        warnings: List[str] = []

        try:
            data = safe_json_loads(text)
            selection = TitleSelection.model_validate(data)
            return selection, warnings
        except Exception as exc:
            warnings.append(f"Title selection JSON parse failed; repair attempted. Error: {exc}")

        repaired = self._repair_title_select(text)
        if repaired:
            try:
                data = safe_json_loads(repaired)
                selection = TitleSelection.model_validate(data)
                return selection, warnings
            except Exception as exc:
                warnings.append(
                    f"Title selection JSON repair failed; fallback used. Error: {exc}"
                )

        best = max(titles, key=lambda t: t.score)
        return (
            TitleSelection(
                final_title=best.title,
                why_selected="fallback: highest score",
                optimized_reason="fallback: JSON parse failed",
            ),
            warnings,
        )

    def _fallback_titles(self) -> List[TitleCandidate]:
        templates = [
            "减负之后，家长为什么更焦虑？",
            "学校不补课了，家长反而更慌？",
            "孩子少学半小时，真正的差距在哪？",
            "看似减负，竞争却更残酷",
            "真正拉开差距的，从来不是作业量",
            "越强调减负，越不敢松口气",
            "内卷不在学校里，而在家长心里？",
            "政策松了，家长却更紧绷了",
            "升学路上，焦虑来自哪些隐形变量？",
            "减负之下，家庭决策的三大误区",
        ]
        return [
            TitleCandidate(title=title, score=60, reason="fallback", risk="low")
            for title in templates
        ]

    def _repair_title_gen(self, raw_text: str) -> str:
        prompt = (
            "你是 JSON 修复工具。\n"
            "请将以下内容修复为符合指定结构的 JSON，仅输出 JSON。\n\n"
            "结构要求:\n"
            "{\n"
            "  \"titles\": [\n"
            "    {\"title\": \"\", \"score\": 0, \"reason\": \"\", \"risk\": \"\"}\n"
            "  ]\n"
            "}\n\n"
            "待修复内容:\n"
            + (raw_text or "")
        )
        return self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="title_generate_repair",
            temperature=0.1,
        ).strip()

    def _repair_title_select(self, raw_text: str) -> str:
        prompt = (
            "你是 JSON 修复工具。\n"
            "请将以下内容修复为符合指定结构的 JSON，仅输出 JSON。\n\n"
            "结构要求:\n"
            "{\n"
            "  \"final_title\": \"\",\n"
            "  \"why_selected\": \"\",\n"
            "  \"optimized_reason\": \"\"\n"
            "}\n\n"
            "待修复内容:\n"
            + (raw_text or "")
        )
        return self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="title_select_repair",
            temperature=0.1,
        ).strip()
