from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app_constants import DEFAULT_NEWS_TYPE, DEFAULT_TOPIC, VALID_SEARCH_PROVIDERS
from config import load_config
from launcher import run_pipeline
from gui import launch_gui
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

    subparsers.add_parser("gui", help="Open the graphical launcher")

    return parser


def main() -> int:
    if getattr(sys, "frozen", False) and len(sys.argv) == 1:
        sys.argv.append("gui")

    parser = build_parser()
    args = parser.parse_args()
    logger = get_logger()

    if args.command != "run":
        if args.command == "gui":
            launch_gui()
            return 0
        logger.error("Unknown command: %s", args.command)
        return 1

    config = load_config()
    manual_path = Path(args.manual_news) if args.manual_news else None
    search_provider = args.search_provider or config.search_provider

    try:
        output_dir = run_pipeline(
            config=config,
            manual_path=manual_path,
            provider_name=search_provider,
            topic=args.topic,
            news_type=args.news_type,
        )
    except Exception as exc:
        logger.error(str(exc))
        return 1

    logger.info("Outputs written to %s", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
