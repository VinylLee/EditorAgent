from __future__ import annotations

from dataclasses import dataclass
import os

from app_constants import (
    DEFAULT_JSON_MODE,
    DEFAULT_LLM_API_KEY,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SEARCH_PROVIDER,
    DEFAULT_TEMPERATURE,
)
from dotenv import load_dotenv


@dataclass
class AppConfig:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    output_dir: str
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    json_mode: str = DEFAULT_JSON_MODE
    # Search provider config
    search_provider: str = DEFAULT_SEARCH_PROVIDER
    dashscope_api_key: str = ""
    tavily_api_key: str = ""


def load_config() -> AppConfig:
    # Load environment variables first, then apply centralized defaults.
    load_dotenv()

    llm_base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("LMSTUDIO_BASE_URL")
        or os.getenv("DEEPSEEK_BASE_URL")
        or DEFAULT_LLM_BASE_URL
    )
    llm_api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("LMSTUDIO_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or DEFAULT_LLM_API_KEY
    )
    llm_model = (
        os.getenv("LLM_MODEL")
        or os.getenv("LMSTUDIO_MODEL")
        or os.getenv("DEEPSEEK_MODEL")
        or DEFAULT_LLM_MODEL
    )
    output_dir = os.getenv("OUTPUT_DIR", DEFAULT_OUTPUT_DIR)
    temperature = float(os.getenv("LLM_TEMPERATURE", str(DEFAULT_TEMPERATURE)))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
    json_mode = os.getenv("LLM_JSON_MODE", DEFAULT_JSON_MODE).strip().lower()
    search_provider = os.getenv("SEARCH_PROVIDER", DEFAULT_SEARCH_PROVIDER).strip().lower()
    dashscope_api_key = os.getenv("DASHSCOPE_API_KEY", "")
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")

    return AppConfig(
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        output_dir=output_dir,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=json_mode,
        search_provider=search_provider,
        dashscope_api_key=dashscope_api_key,
        tavily_api_key=tavily_api_key,
    )
