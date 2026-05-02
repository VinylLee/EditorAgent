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

DEFAULT_TEMPERATURE = 0.35
DEFAULT_MAX_TOKENS = 16384
DEFAULT_LONG_FORM_MAX_TOKENS = 16384
DEFAULT_JSON_MODE = "off"
DEFAULT_SEARCH_PROVIDER = "auto"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# Semantic dedup defaults
DEFAULT_ENABLE_SEMANTIC_DEDUP = True
DEFAULT_DEDUP_SIMILARITY_THRESHOLD = 0.86
DEFAULT_DEDUP_TITLE_THRESHOLD = 0.8
DEFAULT_DEDUP_RECENT_DAYS = 30

# Search provider constants
DASHSCOPE_SEARCH_MODEL = "qwen-plus"
TAVILY_API_URL = "https://api.tavily.com/search"
PLACEHOLDER_URL_MARKERS = ("example.com", "example", "mock", "模拟", "test.com", "localhost")

# Markdown fragments
REFERENCE_SECTION_HEADER = "**参考来源：**"

# Review thresholds (based on total non-whitespace chars, not just CJK)
ARTICLE_WORD_COUNT_MIN = 1800
ARTICLE_WORD_COUNT_TARGET = 2100
ARTICLE_WORD_COUNT_MAX = 2300
ARTICLE_WORD_COUNT_REVIEW_MAX = 2300	
MAX_REVIEW_ROUNDS = 5

# Per-section word count targets (used in ARTICLE_WRITE_PROMPT)
SECTION_NEWS_INTRO = 200
SECTION_REVERSE_QUESTION = 300
SECTION_SURFACE_ANALYSIS = 300
SECTION_DEEP_ANALYSIS = 400
SECTION_PARENT_ANXIETY = 400
SECTION_ADVICE_TOTAL = 400
SECTION_ADVICE_EACH_MIN = 100
SECTION_ADVICE_EACH_MAX = 150
SECTION_ENDING = 100