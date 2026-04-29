from __future__ import annotations

import json
import re
from typing import Any


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


def _extract_json_block(text: str) -> str:
    text = _strip_code_fences(text)
    match = re.search(r"[\{\[]", text)
    if not match:
        return ""
    start = match.start()
    end_obj = text.rfind("}")
    end_arr = text.rfind("]")
    end = max(end_obj, end_arr)
    if end <= start:
        return ""
    return text[start : end + 1]


def safe_json_loads(text: str) -> Any:
    candidate = _extract_json_block(text)
    if not candidate:
        raise ValueError("No JSON block found in LLM output.")
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        return json.loads(candidate)
