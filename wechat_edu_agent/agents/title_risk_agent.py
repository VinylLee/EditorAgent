from __future__ import annotations

import json
import re
from typing import List, Tuple

from llm.json_schemas import TITLE_RISK_SCHEMA
from llm.prompts import SYSTEM_PROMPT, TITLE_RISK_PROMPT
from models.schemas import FactExtractResult, TitleCandidate, TitleRiskItem, TitleRiskResult
from utils.json_utils import safe_json_loads


class TitleRiskAgent:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def assess(
        self,
        titles: List[TitleCandidate],
        article_markdown: str,
        fact_extract: FactExtractResult,
    ) -> Tuple[TitleRiskResult, List[str]]:
        prompt = (
            TITLE_RISK_PROMPT
            + "\n\n候选标题:\n"
            + json.dumps([t.model_dump() for t in titles], ensure_ascii=False, indent=2)
            + "\n\n文章内容:\n"
            + (article_markdown or "")
            + "\n\n事实抽取结果:\n"
            + json.dumps(fact_extract.model_dump(), ensure_ascii=False, indent=2)
        )
        text = self.llm_client.chat_json(
            SYSTEM_PROMPT,
            prompt,
            json_schema=TITLE_RISK_SCHEMA,
            request_tag="title_risk",
            temperature=0.1,
        )
        warnings: List[str] = []

        try:
            data = safe_json_loads(text)
            result = TitleRiskResult.model_validate(data)
            return self._normalize(result, titles), warnings
        except Exception as exc:
            warnings.append(f"Title risk JSON parse failed; repair attempted. Error: {exc}")

        repaired = self._repair_json(text)
        if repaired:
            try:
                data = safe_json_loads(repaired)
                result = TitleRiskResult.model_validate(data)
                return self._normalize(result, titles), warnings
            except Exception as exc:
                warnings.append(f"Title risk JSON repair failed; fallback used. Error: {exc}")

        return self._fallback(titles), warnings

    def _normalize(
        self, result: TitleRiskResult, titles: List[TitleCandidate]
    ) -> TitleRiskResult:
        all_titles = {t.title for t in titles}
        safe_titles = [t for t in result.safe_titles if t in all_titles]
        risky_titles = [r for r in result.risky_titles if r.title in all_titles]
        recommended = result.recommended_title if result.recommended_title in all_titles else ""
        if not recommended and safe_titles:
            recommended = safe_titles[0]
        elif not recommended and titles:
            recommended = titles[0].title
        return TitleRiskResult(
            safe_titles=safe_titles,
            risky_titles=risky_titles,
            recommended_title=recommended,
        )

    def _repair_json(self, raw_text: str) -> str:
        prompt = (
            "你是 JSON 修复工具。\n"
            "请将以下内容修复为符合指定结构的 JSON，仅输出 JSON。\n\n"
            "结构要求:\n"
            "{\n"
            "  \"safe_titles\": [],\n"
            "  \"risky_titles\": [\n"
            "    {\"title\": \"\", \"risk_level\": \"low|medium|high\", "
            "\"reason\": \"\", \"suggested_fix\": \"\"}\n"
            "  ],\n"
            "  \"recommended_title\": \"\"\n"
            "}\n\n"
            "待修复内容:\n"
            + (raw_text or "")
        )
        return self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="title_risk_repair",
            temperature=0.1,
        ).strip()

    def _fallback(self, titles: List[TitleCandidate]) -> TitleRiskResult:
        risky: List[TitleRiskItem] = []
        safe: List[str] = []
        for item in titles:
            risk_level, reason = self._heuristic_risk(item.title)
            if risk_level == "low":
                safe.append(item.title)
            else:
                risky.append(
                    TitleRiskItem(
                        title=item.title,
                        risk_level=risk_level,
                        reason=reason,
                        suggested_fix="弱化绝对化或去掉数字",
                    )
                )
        recommended = safe[0] if safe else (titles[0].title if titles else "")
        return TitleRiskResult(
            safe_titles=safe,
            risky_titles=risky,
            recommended_title=recommended,
        )

    def _heuristic_risk(self, title: str) -> Tuple[str, str]:
        if re.search(r"\d", title) or "%" in title or "百分之" in title:
            return "high", "包含具体数字或比例"
        absolute_terms = [
            "一定",
            "注定",
            "彻底",
            "毁掉",
            "没机会",
            "必然",
            "唯一",
            "绝对",
            "无法",
            "毫无",
        ]
        if any(term in title for term in absolute_terms):
            return "high", "包含绝对化表述"
        panic_terms = ["恐慌", "崩溃", "灾难", "失控", "崩盘", "断崖"]
        if any(term in title for term in panic_terms):
            return "medium", "包含恐慌化措辞"
        return "low", ""
