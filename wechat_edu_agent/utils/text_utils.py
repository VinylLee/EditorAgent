from __future__ import annotations

import re


def slugify(text: str, fallback: str = "manual") -> str:
    text = (text or "").strip()
    text = re.sub(r'[\s/\\:<>"|?*]+', "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_")
    return text or fallback


def count_text_chars(text: str) -> int:
    """Count all non-whitespace characters (standard Chinese \u5b57\u6570\u7edf\u8ba1)."""
    return len(re.sub(r"\s", "", text or ""))
