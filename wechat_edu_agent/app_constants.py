"""Centralized application constants.

This module keeps project-wide defaults and provider constants in one place so
they are easier to manage without changing runtime behavior.
"""

from __future__ import annotations

# CLI and search provider options
VALID_SEARCH_PROVIDERS = ("manual", "dashscope", "tavily", "auto")
DEFAULT_TOPIC = "教育内卷"
DEFAULT_NEWS_TYPE = "社会事件"

# App configuration defaults
# LLM defaults can be overridden by multiple env vars for compatibility with different platforms (e.g. LMSTUDIO_*, DEEPSEEK_*)
DEFAULT_LLM_BASE_URL = "http://localhost:1234/v1"
DEFAULT_LLM_API_KEY = "lm-studio"
DEFAULT_LLM_MODEL = "qwen3.5-9b"
DEFAULT_OUTPUT_DIR = "outputs"

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 16384
DEFAULT_LONG_FORM_MAX_TOKENS = 16384
DEFAULT_JSON_MODE = "off"
DEFAULT_SEARCH_PROVIDER = "auto"
# Semantic dedup defaults
DEFAULT_ENABLE_SEMANTIC_DEDUP = True
DEFAULT_DEDUP_SIMILARITY_THRESHOLD = 0.86
DEFAULT_DEDUP_TITLE_THRESHOLD = 0.8
DEFAULT_DEDUP_RECENT_DAYS = 30

# Search provider constants
TAVILY_API_URL = "https://api.tavily.com/search"
PLACEHOLDER_URL_MARKERS = ("example.com", "example", "mock", "模拟", "test.com", "localhost")

# Markdown fragments
REFERENCE_SECTION_HEADER = "**参考来源：**"

# Review thresholds
ARTICLE_WORD_COUNT_MIN = 2000
ARTICLE_WORD_COUNT_MAX = 2200
ARTICLE_WORD_COUNT_TARGET = 2600
ARTICLE_WORD_COUNT_REVIEW_MAX = 2600
MAX_REVIEW_ROUNDS = 3