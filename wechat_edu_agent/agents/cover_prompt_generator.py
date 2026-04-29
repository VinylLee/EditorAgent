from __future__ import annotations

from typing import List, Tuple

from llm.json_schemas import COVER_PROMPT_SCHEMA
from llm.prompts import COVER_PROMPT_GEN_PROMPT, SYSTEM_PROMPT
from models.schemas import CoverPrompt
from utils.json_utils import safe_json_loads


class CoverPromptGenerator:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def generate(self, final_title: str, article: str) -> Tuple[CoverPrompt, List[str]]:
        prompt = (
            COVER_PROMPT_GEN_PROMPT
            + "\n\n文章标题:\n"
            + final_title
            + "\n\n文章内容:\n"
            + article
        )
        text = self.llm_client.chat_json(
            SYSTEM_PROMPT,
            prompt,
            json_schema=COVER_PROMPT_SCHEMA,
            request_tag="cover_prompt",
        )
        warnings: List[str] = []

        try:
            data = safe_json_loads(text)
            cover = CoverPrompt.model_validate(data)
            return cover, warnings
        except Exception as exc:
            warnings.append(f"Cover prompt JSON parse failed; repair attempted. Error: {exc}")

        repaired = self._repair_json(text)
        if repaired:
            try:
                data = safe_json_loads(repaired)
                cover = CoverPrompt.model_validate(data)
                return cover, warnings
            except Exception as exc:
                warnings.append(
                    f"Cover prompt JSON repair failed; fallback used. Error: {exc}"
                )

        return self._fallback(final_title), warnings

    def _fallback(self, final_title: str) -> CoverPrompt:
        return CoverPrompt(
            cover_prompt_cn=(
                "教育竞争场景，教室或书桌，作业本与时钟，"
                "家长剪影在旁，氛围理性紧张，城市中产家庭，"
                "插画风格，清爽配色"
            ),
            cover_prompt_en=(
                "Education competition scene, classroom or desk, notebooks and a clock, "
                "parent silhouette nearby, rational tense mood, urban middle-class family, "
                "illustration style, clean palette"
            ),
            negative_prompt="real person, logo, watermark, celebrity, brand, gore",
            suggested_layout="Left text block, right illustration, clear focal point",
            cover_text=final_title[:10],
        )

    def _repair_json(self, raw_text: str) -> str:
        prompt = (
            "你是 JSON 修复工具。\n"
            "请将以下内容修复为符合指定结构的 JSON，仅输出 JSON。\n\n"
            "结构要求:\n"
            "{\n"
            "  \"cover_prompt_cn\": \"\",\n"
            "  \"cover_prompt_en\": \"\",\n"
            "  \"negative_prompt\": \"\",\n"
            "  \"suggested_layout\": \"\",\n"
            "  \"cover_text\": \"\"\n"
            "}\n\n"
            "待修复内容:\n"
            + (raw_text or "")
        )
        return self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="cover_prompt_repair",
            temperature=0.1,
        ).strip()
