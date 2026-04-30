from __future__ import annotations

from pathlib import Path

from app_constants import VALID_SEARCH_PROVIDERS
from agents.workflow import Workflow
from config import AppConfig
from llm.client import LLMClient
from search.aggregator import SearchAggregator
from search.base import SearchProvider
from search.dashscope_search import DashScopeSearchProvider
from search.manual_input import ManualNewsProvider
from search.tavily_search import TavilySearchProvider
from utils.logger import get_logger


def build_provider(
    config: AppConfig,
    manual_path: Path | None,
    provider_name: str,
    news_type: str,
) -> SearchProvider:
    logger = get_logger()

    if manual_path:
        logger.info("Using manual news: %s", manual_path)
        return ManualNewsProvider(manual_path, news_type=news_type)

    if provider_name == "manual":
        message = "No manual news file provided. Use a file path or choose another search provider."
        logger.error(message)
        raise RuntimeError(message)

    if provider_name == "dashscope":
        if not config.dashscope_api_key:
            message = "DASHSCOPE_API_KEY not set in .env"
            logger.error(message)
            raise RuntimeError(message)
        logger.info("Using DashScope search provider")
        return DashScopeSearchProvider(api_key=config.dashscope_api_key)

    if provider_name == "tavily":
        if not config.tavily_api_key:
            message = "TAVILY_API_KEY not set in .env"
            logger.error(message)
            raise RuntimeError(message)
        logger.info("Using Tavily search provider")
        return TavilySearchProvider(api_key=config.tavily_api_key)

    if provider_name == "auto":
        providers: list[SearchProvider] = []
        if config.dashscope_api_key:
            providers.append(DashScopeSearchProvider(api_key=config.dashscope_api_key))
        if config.tavily_api_key:
            providers.append(TavilySearchProvider(api_key=config.tavily_api_key))
        if not providers:
            message = "auto search requires DASHSCOPE_API_KEY or TAVILY_API_KEY in .env"
            logger.error(message)
            raise RuntimeError(message)
        logger.info(
            "Using auto search with %d provider(s): %s",
            len(providers),
            ", ".join(type(p).__name__ for p in providers),
        )
        return SearchAggregator(providers=providers)

    message = f"Unknown search provider: {provider_name}"
    logger.error(message)
    raise RuntimeError(message)


def run_pipeline(
    config: AppConfig,
    manual_path: Path | None,
    provider_name: str,
    topic: str,
    news_type: str,
) -> Path:
    if provider_name not in VALID_SEARCH_PROVIDERS:
        raise ValueError(
            f"Invalid search provider '{provider_name}'. Choices: {', '.join(VALID_SEARCH_PROVIDERS)}"
        )

    if manual_path and not manual_path.exists():
        raise FileNotFoundError(f"Manual news file not found: {manual_path}")

    provider = build_provider(
        config=config,
        manual_path=manual_path,
        provider_name=provider_name,
        news_type=news_type,
    )

    llm_client = LLMClient.from_config(config)
    workflow = Workflow(llm_client, output_dir=config.output_dir)
    return workflow.run(provider=provider, topic=topic, news_type=news_type)