from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app_constants import DEFAULT_NEWS_TYPE, DEFAULT_TOPIC, VALID_SEARCH_PROVIDERS
from agents.workflow import Workflow
from config import AppConfig, load_config
from llm.client import LLMClient
from search.aggregator import SearchAggregator
from search.base import SearchProvider
from search.dashscope_search import DashScopeSearchProvider
from search.manual_input import ManualNewsProvider
from search.tavily_search import TavilySearchProvider
from utils.logger import get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WeChat education content agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the content pipeline")
    run_parser.add_argument(
        "--manual-news",
        help="Path to manual news text file (overrides search provider)",
    )
    run_parser.add_argument(
        "--search-provider",
        choices=VALID_SEARCH_PROVIDERS,
        help="Search provider: dashscope, tavily, auto, manual. Default from SEARCH_PROVIDER env.",
    )
    run_parser.add_argument(
        "--topic", default=DEFAULT_TOPIC, help="Topic keyword for search and output folder"
    )
    run_parser.add_argument(
        "--news-type", default=DEFAULT_NEWS_TYPE, help="新闻类型: 教育部政策/学校案例/社会事件"
    )

    return parser


def _build_provider(
    config: AppConfig,
    manual_path: Path | None,
    provider_name: str,
    news_type: str,
) -> SearchProvider:
    logger = get_logger()

    # --manual-news always wins over search providers
    if manual_path:
        logger.info("Using manual news: %s", manual_path)
        return ManualNewsProvider(manual_path, news_type=news_type)

    if provider_name == "manual":
        logger.error(
            "No --manual-news path provided. "
            "Use --manual-news <file> or choose another --search-provider."
        )
        raise SystemExit(1)

    if provider_name == "dashscope":
        if not config.dashscope_api_key:
            logger.error("DASHSCOPE_API_KEY not set in .env")
            raise SystemExit(1)
        logger.info("Using DashScope search provider")
        return DashScopeSearchProvider(api_key=config.dashscope_api_key)

    if provider_name == "tavily":
        if not config.tavily_api_key:
            logger.error("TAVILY_API_KEY not set in .env")
            raise SystemExit(1)
        logger.info("Using Tavily search provider")
        return TavilySearchProvider(api_key=config.tavily_api_key)

    if provider_name == "auto":
        providers: list[SearchProvider] = []
        if config.dashscope_api_key:
            providers.append(DashScopeSearchProvider(api_key=config.dashscope_api_key))
        if config.tavily_api_key:
            providers.append(TavilySearchProvider(api_key=config.tavily_api_key))
        if not providers:
            logger.error(
                "auto search requires DASHSCOPE_API_KEY or TAVILY_API_KEY in .env"
            )
            raise SystemExit(1)
        logger.info(
            "Using auto search with %d provider(s): %s",
            len(providers),
            ", ".join(type(p).__name__ for p in providers),
        )
        return SearchAggregator(providers=providers)

    logger.error("Unknown search provider: %s", provider_name)
    raise SystemExit(1)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logger = get_logger()

    if args.command != "run":
        logger.error("Unknown command: %s", args.command)
        return 1

    config = load_config()
    manual_path = Path(args.manual_news) if args.manual_news else None

    if manual_path and not manual_path.exists():
        logger.error("Manual news file not found: %s", manual_path)
        return 1

    search_provider = args.search_provider or config.search_provider
    if search_provider not in VALID_SEARCH_PROVIDERS:
        logger.error(
            "Invalid search provider '%s'. Choices: %s",
            search_provider,
            ", ".join(VALID_SEARCH_PROVIDERS),
        )
        return 1

    provider = _build_provider(
        config=config,
        manual_path=manual_path,
        provider_name=search_provider,
        news_type=args.news_type,
    )

    llm_client = LLMClient.from_config(config)
    workflow = Workflow(llm_client, output_dir=config.output_dir)

    output_dir = workflow.run(provider=provider, topic=args.topic, news_type=args.news_type)
    logger.info("Outputs written to %s", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
