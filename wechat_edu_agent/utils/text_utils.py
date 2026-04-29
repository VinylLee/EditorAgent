from __future__ import annotations

import re


def slugify(text: str, fallback: str = "manual") -> str:
    text = (text or "").strip()
    text = re.sub(r'[\s/\\:<>"|?*]+', "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_")
    return text or fallback


def count_cjk_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))
