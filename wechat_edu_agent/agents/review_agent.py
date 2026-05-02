from __future__ import annotations

import json
from typing import List, Tuple

from app_constants import (
    ARTICLE_WORD_COUNT_MAX,
    ARTICLE_WORD_COUNT_MIN,
    ARTICLE_WORD_COUNT_REVIEW_MAX,
    DEFAULT_LONG_FORM_MAX_TOKENS,
)
from llm.json_schemas import REVIEW_SCHEMA
from llm.prompts import REVIEW_PROMPT, REWRITE_PROMPT, SYSTEM_PROMPT
from models.schemas import FactExtractResult, ReviewResult, TitleRiskResult
from utils.json_utils import safe_json_loads
from utils.text_utils import count_cjk_chars


class ReviewAgent:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def review(
        self,
        final_title: str,
        article_markdown: str,
        fact_extract: FactExtractResult,
        title_risk: TitleRiskResult,
        raw_text: str,
    ) -> Tuple[ReviewResult, List[str]]:
        fact_json = json.dumps(fact_extract.model_dump(), ensure_ascii=False, indent=2)
        title_json = json.dumps(title_risk.model_dump(), ensure_ascii=False, indent=2)
        prompt = (
            REVIEW_PROMPT
            + "\n\n文章标题:\n"
            + final_title
            + "\n\n文章正文:\n"
            + (article_markdown or "")
            + "\n\n事实抽取结果:\n"
            + fact_json
            + "\n\n标题风控结果:\n"
            + title_json
            + "\n\n新闻原文:\n"
            + (raw_text or "")
        )
        text = self.llm_client.chat_json(
            SYSTEM_PROMPT,
            prompt,
            json_schema=REVIEW_SCHEMA,
            request_tag="article_review",
            temperature=0.1,
        )
        warnings: List[str] = []

        try:
            data = safe_json_loads(text)
            normalized = self._normalize_review_data(data)
            review = ReviewResult.model_validate(normalized)
            review = self._apply_rules(review, article_markdown, title_risk)
            return review, warnings
        except Exception as exc:
            warnings.append(f"Review JSON parse failed; repair attempted. Error: {exc}")

        repaired = self._repair_json(text)
        if repaired:
            try:
                data = safe_json_loads(repaired)
                normalized = self._normalize_review_data(data)
                review = ReviewResult.model_validate(normalized)
                review = self._apply_rules(review, article_markdown, title_risk)
                return review, warnings
            except Exception as exc:
                warnings.append(f"Review JSON repair failed; fallback used. Error: {exc}")

        return self._fallback(article_markdown, title_risk), warnings

    def rewrite(
        self,
        final_title: str,
        article_markdown: str,
        review: ReviewResult,
        fact_extract: FactExtractResult,
        raw_text: str,
    ) -> Tuple[str, List[str]]:
        fact_json = json.dumps(fact_extract.model_dump(), ensure_ascii=False, indent=2)
        prompt = (
            REWRITE_PROMPT
            + "\n\n指定标题:\n"
            + final_title
            + "\n\n修正要求:\n"
            + (review.rewrite_instructions or "")
            + "\n\n原始文章:\n"
            + (article_markdown or "")
            + "\n\n事实抽取结果:\n"
            + fact_json
            + "\n\n新闻原文:\n"
            + (raw_text or "")
        )
        text = self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="article_rewrite",
            max_tokens=DEFAULT_LONG_FORM_MAX_TOKENS,
        ).strip()
        warnings: List[str] = []
        if not text:
            warnings.append("Article rewrite returned empty content; fallback used.")
            return article_markdown, warnings
        if getattr(self.llm_client, "last_finish_reason", None) == "length":
            warnings.append("Article rewrite was truncated by token limit; fallback used.")
            return article_markdown, warnings
        return text, warnings

    def _repair_json(self, raw_text: str) -> str:
        prompt = (
            "你是 JSON 修复工具。\n"
            "请将以下内容修复为符合指定结构的 JSON，仅输出 JSON。\n\n"
            "结构要求:\n"
            "{\n"
            "  \"passed\": false,\n"
            "  \"score\": 0,\n"
            "  \"rewrite_required\": true,\n"
            "  \"problems\": [],\n"
            "  \"hallucination_risks\": [],\n"
            "  \"unsupported_claims\": [],\n"
            "  \"title_risks\": [],\n"
            "  \"rewrite_instructions\": \"\",\n"
            "  \"human_check_required\": true\n"
            "}\n\n"
            "待修复内容:\n"
            + (raw_text or "")
        )
        return self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="review_repair",
            temperature=0.1,
        ).strip()

    def _fallback(
        self, article_markdown: str, title_risk: TitleRiskResult
    ) -> ReviewResult:
        word_count = count_cjk_chars(article_markdown)
        problems: List[str] = ["Review JSON parse failed"]
        rewrite_required = False

        if word_count < ARTICLE_WORD_COUNT_MIN or word_count > ARTICLE_WORD_COUNT_MAX:
            rewrite_required = True
            problems.append(f"字数不在 {ARTICLE_WORD_COUNT_MIN}-{ARTICLE_WORD_COUNT_MAX} 范围内（当前 {word_count} 字）")

        if self._markdown_abnormal(article_markdown):
            rewrite_required = True
            problems.append("Markdown 存在异常格式")

        high_risk_titles = self._extract_high_risk_titles(title_risk)

        return ReviewResult(
            passed=False,
            score=40,
            rewrite_required=rewrite_required,
            problems=problems,
            hallucination_risks=[],
            unsupported_claims=[],
            title_risks=high_risk_titles,
            rewrite_instructions=f"当前文章实际 {word_count} 字，目标范围 {ARTICLE_WORD_COUNT_MIN}-{ARTICLE_WORD_COUNT_MAX} 字。请按事实抽取结果修正文章，并根据需要增删内容。",
            human_check_required=True,
        )

    def _apply_rules(
        self,
        review: ReviewResult,
        article_markdown: str,
        title_risk: TitleRiskResult,
    ) -> ReviewResult:
        word_count = count_cjk_chars(article_markdown)
        if word_count < ARTICLE_WORD_COUNT_MIN or word_count > ARTICLE_WORD_COUNT_REVIEW_MAX:
            review.rewrite_required = True
            review.problems.append(f"字数不在 {ARTICLE_WORD_COUNT_MIN}-{ARTICLE_WORD_COUNT_REVIEW_MAX} 范围内（当前 {word_count} 字）")
            if word_count < ARTICLE_WORD_COUNT_MIN:
                wc_hint = f"当前文章实际 {word_count} 字，比目标下限 {ARTICLE_WORD_COUNT_MIN} 字少 {ARTICLE_WORD_COUNT_MIN - word_count} 字，请在修正时充实内容。"
            else:
                wc_hint = f"当前文章实际 {word_count} 字，超过目标上限 {ARTICLE_WORD_COUNT_MAX} 字，请在修正时精简内容。"
            review.rewrite_instructions = (
                (review.rewrite_instructions + "\n" if review.rewrite_instructions else "")
                + wc_hint
            )

        if self._markdown_abnormal(article_markdown):
            review.rewrite_required = True
            review.problems.append("Markdown 存在异常格式")

        # Note: title_risk agent results are already in the review LLM context.
        # The review evaluates titles itself — do not cascade title_risk into review verdict.

        if review.hallucination_risks:
            review.passed = False

        # Unsupported claims: soft warning, not hard fail
        if review.unsupported_claims:
            for claim in review.unsupported_claims:
                review.problems.append(f"缺乏事实支撑的断言: {claim}")
            review.unsupported_claims = []

        if any("high" in risk.lower() for risk in review.title_risks):
            review.passed = False

        # Score: <70 hard fail, 70-84 soft rewrite
        if review.score < 70:
            review.passed = False
        elif review.score < 85:
            review.rewrite_required = True
            if not review.problems and not review.hallucination_risks:
                review.problems.append("分数在70-84之间，建议优化结构和措辞")

        review.human_check_required = (
            not review.passed
            or bool(review.hallucination_risks)
        )
        if review.rewrite_required and not review.rewrite_instructions:
            review.rewrite_instructions = (
                "请依据事实抽取结果修正文章，删除无法验证的具体事实和数字。"
            )
        return review

    def _normalize_review_data(self, data: object) -> dict:
        if not isinstance(data, dict):
            return {}

        return {
            "passed": bool(data.get("passed", False)),
            "score": self._coerce_int(data.get("score", 0)),
            "rewrite_required": bool(data.get("rewrite_required", False)),
            "problems": self._normalize_string_list(data.get("problems")),
            "hallucination_risks": self._normalize_string_list(
                data.get("hallucination_risks")
            ),
            "unsupported_claims": self._normalize_string_list(
                data.get("unsupported_claims")
            ),
            "title_risks": self._normalize_title_risks(data.get("title_risks")),
            "rewrite_instructions": str(data.get("rewrite_instructions") or ""),
            "human_check_required": bool(data.get("human_check_required", False)),
        }

    def _normalize_string_list(self, items: object) -> List[str]:
        if not isinstance(items, list):
            return []
        results: List[str] = []
        for item in items:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    results.append(text)
                continue
            if isinstance(item, dict):
                text = (
                    item.get("text")
                    or item.get("reason")
                    or item.get("detail")
                    or item.get("claim")
                )
                if text:
                    results.append(str(text).strip())
                continue
            text = str(item).strip()
            if text:
                results.append(text)
        return results

    def _normalize_title_risks(self, items: object) -> List[str]:
        if not isinstance(items, list):
            return []
        results: List[str] = []
        for item in items:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    results.append(text)
                continue
            if isinstance(item, dict):
                title = str(item.get("title") or "").strip()
                level = str(item.get("risk_level") or "").strip() or "medium"
                reason = str(item.get("reason") or "").strip()
                parts = [level, title]
                if reason:
                    parts.append(reason)
                results.append(": ".join(p for p in parts if p))
                continue
            text = str(item).strip()
            if text:
                results.append(text)
        return results

    def _coerce_int(self, value: object) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    def _markdown_abnormal(self, text: str) -> bool:
        stripped = text or ""
        if "```" in stripped or "'''" in stripped:
            return True
        return False

    def _extract_high_risk_titles(self, title_risk: TitleRiskResult) -> List[str]:
        risks: List[str] = []
        for item in title_risk.risky_titles:
            if item.risk_level.lower() == "high":
                risks.append(f"high: {item.title}")
        return risks
