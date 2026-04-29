from __future__ import annotations

from typing import List, Tuple

from llm.json_schemas import FACT_EXTRACT_SCHEMA
from llm.prompts import FACT_EXTRACT_PROMPT, SYSTEM_PROMPT
from models.schemas import FactExtractResult
from utils.json_utils import safe_json_loads


class FactExtractAgent:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def extract(self, raw_text: str) -> Tuple[FactExtractResult, List[str]]:
        prompt = FACT_EXTRACT_PROMPT + "\n\n新闻原文:\n" + (raw_text or "")
        text = self.llm_client.chat_json(
            SYSTEM_PROMPT,
            prompt,
            json_schema=FACT_EXTRACT_SCHEMA,
            request_tag="fact_extract",
            temperature=0.1,
        )
        warnings: List[str] = []

        try:
            data = safe_json_loads(text)
            normalized = self._normalize_data(data)
            return FactExtractResult.model_validate(normalized), warnings
        except Exception as exc:
            warnings.append(f"Fact extract JSON parse failed; repair attempted. Error: {exc}")

        repaired = self._repair_json(text)
        if repaired:
            try:
                data = safe_json_loads(repaired)
                normalized = self._normalize_data(data)
                return FactExtractResult.model_validate(normalized), warnings
            except Exception as exc:
                warnings.append(f"Fact extract JSON repair failed; fallback used. Error: {exc}")

        return self._fallback(), warnings

    def _repair_json(self, raw_text: str) -> str:
        prompt = (
            "你是 JSON 修复工具。\n"
            "请将以下内容修复为符合指定结构的 JSON，仅输出 JSON。\n\n"
            "结构要求:\n"
            "{\n"
            "  \"verified_facts\": [{\"id\": \"F1\", \"fact\": \"\", \"evidence\": \"\"}],\n"
            "  \"verified_numbers\": [{\"id\": \"N1\", \"number\": \"\", \"meaning\": \"\", \"evidence\": \"\"}],\n"
            "  \"verified_quotes\": [{\"id\": \"Q1\", \"quote\": \"\", \"speaker\": \"\", \"evidence\": \"\"}],\n"
            "  \"allowed_inferences\": [],\n"
            "  \"forbidden_claims\": [],\n"
            "  \"uncertain_points\": []\n"
            "}\n\n"
            "待修复内容:\n"
            + (raw_text or "")
        )
        return self.llm_client.chat_text(
            SYSTEM_PROMPT,
            prompt,
            request_tag="fact_extract_repair",
            temperature=0.1,
        ).strip()

    def _normalize_data(self, data: object) -> dict:
        if not isinstance(data, dict):
            return {}

        normalized = {
            "verified_facts": self._normalize_fact_list(data.get("verified_facts")),
            "verified_numbers": self._normalize_number_list(
                data.get("verified_numbers")
            ),
            "verified_quotes": self._normalize_quote_list(data.get("verified_quotes")),
            "allowed_inferences": self._normalize_string_list(
                data.get("allowed_inferences")
            ),
            "forbidden_claims": self._normalize_string_list(
                data.get("forbidden_claims")
            ),
            "uncertain_points": self._normalize_string_list(
                data.get("uncertain_points")
            ),
        }
        return normalized

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
                    item.get("inference")
                    or item.get("text")
                    or item.get("claim")
                    or item.get("point")
                    or item.get("reason")
                )
                if not text:
                    continue
                text = str(text).strip()
                if text:
                    results.append(text)
                continue
            text = str(item).strip()
            if text:
                results.append(text)
        return results

    def _normalize_fact_list(self, items: object) -> List[dict]:
        if not isinstance(items, list):
            return []
        results: List[dict] = []
        for idx, item in enumerate(items, start=1):
            if isinstance(item, dict):
                fact = str(item.get("fact") or item.get("text") or "").strip()
                evidence = str(item.get("evidence") or "").strip()
                if not fact:
                    continue
                fid = str(item.get("id") or f"F{idx}")
                results.append({"id": fid, "fact": fact, "evidence": evidence})
                continue
            if isinstance(item, str):
                fact = item.strip()
                if fact:
                    results.append({"id": f"F{idx}", "fact": fact, "evidence": ""})
        return results

    def _normalize_number_list(self, items: object) -> List[dict]:
        if not isinstance(items, list):
            return []
        results: List[dict] = []
        for idx, item in enumerate(items, start=1):
            if isinstance(item, dict):
                number = str(item.get("number") or item.get("value") or "").strip()
                meaning = str(item.get("meaning") or item.get("description") or "").strip()
                evidence = str(item.get("evidence") or "").strip()
                if not number:
                    continue
                nid = str(item.get("id") or f"N{idx}")
                results.append(
                    {
                        "id": nid,
                        "number": number,
                        "meaning": meaning,
                        "evidence": evidence,
                    }
                )
                continue
            if isinstance(item, str):
                number = item.strip()
                if number:
                    results.append(
                        {
                            "id": f"N{idx}",
                            "number": number,
                            "meaning": "",
                            "evidence": "",
                        }
                    )
        return results

    def _normalize_quote_list(self, items: object) -> List[dict]:
        if not isinstance(items, list):
            return []
        results: List[dict] = []
        for idx, item in enumerate(items, start=1):
            if isinstance(item, dict):
                quote = str(item.get("quote") or item.get("text") or "").strip()
                speaker = str(item.get("speaker") or "").strip()
                evidence = str(item.get("evidence") or "").strip()
                if not quote:
                    continue
                qid = str(item.get("id") or f"Q{idx}")
                results.append(
                    {
                        "id": qid,
                        "quote": quote,
                        "speaker": speaker,
                        "evidence": evidence,
                    }
                )
                continue
            if isinstance(item, str):
                quote = item.strip()
                if quote:
                    results.append(
                        {
                            "id": f"Q{idx}",
                            "quote": quote,
                            "speaker": "",
                            "evidence": "",
                        }
                    )
        return results

    def _fallback(self) -> FactExtractResult:
        return FactExtractResult(
            verified_facts=[],
            verified_numbers=[],
            verified_quotes=[],
            allowed_inferences=[],
            forbidden_claims=["事实抽取失败，禁止新增具体事实或数字"],
            uncertain_points=["事实抽取失败，需人工核对"],
        )
