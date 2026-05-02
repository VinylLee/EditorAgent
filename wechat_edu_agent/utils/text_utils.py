from __future__ import annotations

import re

# Prefixes that indicate LLM assistant preamble — must be stripped
BAD_PREFIXES = (
    "好的",
    "根据您的",
    "以下是",
    "我为您",
    "修正后的",
    "根据要求",
    "根据修正",
)


def slugify(text: str, fallback: str = "manual") -> str:
    text = (text or "").strip()
    text = re.sub(r'[\s/\\:<>"|?*]+', "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_")
    return text or fallback


def count_text_chars(text: str) -> int:
    """Count all non-whitespace characters (standard Chinese \u5b57\u6570\u7edf\u8ba1)."""
    return len(re.sub(r"\s", "", text or ""))


def clean_llm_article(text: str) -> str:
    """Strip LLM preamble, code fences, and common artifacts from generated text."""
    text = (text or "").strip()

    # Remove code fences
    text = re.sub(r"^```(?:markdown)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Remove leading horizontal rule
    text = re.sub(r"^---\s*", "", text)

    # Remove assistant preamble: "\u597d\u7684\uff0c\u2026\u2026", "\u6839\u636e\u60a8\u7684\u2026\u2026", etc.
    for prefix in BAD_PREFIXES:
        if text.startswith(prefix):
            # Try to find the first heading or real content
            match = re.search(r"(?:^|\n)(#+\s)", text, re.MULTILINE)
            if match:
                text = text[match.start():]
            break

    return text.strip()
