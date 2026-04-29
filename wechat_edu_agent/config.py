from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass
class AppConfig:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    output_dir: str
    temperature: float = 0.7
    max_tokens: int = 2048
    json_mode: str = "off"
    # Search provider config
    search_provider: str = "manual"
    dashscope_api_key: str = ""
    tavily_api_key: str = ""


def load_config() -> AppConfig:
    load_dotenv()

    llm_base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("LMSTUDIO_BASE_URL")
        or os.getenv("DEEPSEEK_BASE_URL")
        or "http://localhost:1234/v1"
    )
    llm_api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("LMSTUDIO_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or "lm-studio"
    )
    llm_model = (
        os.getenv("LLM_MODEL")
        or os.getenv("LMSTUDIO_MODEL")
        or os.getenv("DEEPSEEK_MODEL")
        or "qwen3.5-9b"
    )
    output_dir = os.getenv("OUTPUT_DIR", "outputs")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    json_mode = os.getenv("LLM_JSON_MODE", "off").strip().lower()
    search_provider = os.getenv("SEARCH_PROVIDER", "manual").strip().lower()
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
