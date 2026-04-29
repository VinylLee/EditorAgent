from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import List

from agents.article_writer import ArticleWriter
from agents.cover_prompt_generator import CoverPromptGenerator
from agents.fact_extract_agent import FactExtractAgent
from agents.formatter import Formatter
from agents.news_selector import NewsSelector
from agents.polish_agent import PolishAgent
from agents.review_agent import ReviewAgent
from agents.title_optimizer import TitleOptimizer
from agents.title_risk_agent import TitleRiskAgent
from app_constants import MAX_REVIEW_ROUNDS, PLACEHOLDER_URL_MARKERS, REFERENCE_SECTION_HEADER
from models.schemas import NewsItem, RunReport
from search.base import SearchProvider
from utils.file_utils import create_run_dir, write_json, write_text
from utils.logger import get_logger
from utils.text_utils import count_cjk_chars


class Workflow:
    def __init__(self, llm_client, output_dir: str) -> None:
        self.llm_client = llm_client
        self.output_dir = output_dir
        self.news_selector = NewsSelector(llm_client)
        self.fact_extract_agent = FactExtractAgent(llm_client)
        self.article_writer = ArticleWriter(llm_client)
        self.title_optimizer = TitleOptimizer(llm_client)
        self.title_risk_agent = TitleRiskAgent(llm_client)
        self.cover_prompt_generator = CoverPromptGenerator(llm_client)
        self.formatter = Formatter()
        self.review_agent = ReviewAgent(llm_client)
        self.polish_agent = PolishAgent(llm_client)

    def run(self, provider: SearchProvider, topic: str, news_type: str) -> Path:
        logger = get_logger()
        warnings: List[str] = []

        run_dir = create_run_dir(self.output_dir, topic)
        self.llm_client.set_trace_path(run_dir / "llm_trace.jsonl")
        logger.info("Run started. Output dir: %s", run_dir)

        logger.info("Searching news. topic=%s, news_type=%s", topic, news_type)
        search_result = provider.search(topic=topic, news_type=news_type, limit=5)
        if not search_result.items:
            raise ValueError("No news items found from provider.")
        logger.info(
            "Search done. provider=%s, items=%d",
            search_result.provider,
            len(search_result.items),
        )

        write_json(run_dir / "search_result.json", search_result.model_dump())
        logger.info("Search result saved to %s", run_dir / "search_result.json")

        logger.info("Selecting news from %d candidates", len(search_result.items))
        selection_result, warning = self.news_selector.select(search_result.items)
        warnings.extend(warning)
        selected = selection_result.selected_news
        article_angle = selection_result.suggested_article_angle
        logger.info("Selected news title: %s", selected.title)

        logger.info("Extracting facts from raw news text")
        fact_extract, warning = self.fact_extract_agent.extract(search_result.raw_text)
        warnings.extend(warning)
        logger.info(
            "Fact extract done. facts=%d, numbers=%d, quotes=%d",
            len(fact_extract.verified_facts),
            len(fact_extract.verified_numbers),
            len(fact_extract.verified_quotes),
        )

        logger.info("Writing article draft with LLM")
        article, warning = self.article_writer.write(
            selected,
            raw_text=search_result.raw_text,
            fact_extract=fact_extract,
            article_angle=article_angle,
            source_list=search_result.items,
        )
        warnings.extend(warning)
        logger.info(
            "Article draft ready. cjk_chars=%d, preview=%s",
            count_cjk_chars(article),
            self._preview_text(article),
        )

        logger.info("Generating title candidates")
        titles, warning = self.title_optimizer.generate_titles(article)
        warnings.extend(warning)
        logger.info("Titles generated: %d", len(titles))
        if titles:
            preview_titles = ", ".join(t.title for t in titles[:3])
            logger.info("Title preview: %s", preview_titles)

        logger.info("Assessing title risks")
        title_risk, warning = self.title_risk_agent.assess(
            titles, article_markdown=article, fact_extract=fact_extract
        )
        warnings.extend(warning)
        logger.info(
            "Title risk done. safe=%d, risky=%d",
            len(title_risk.safe_titles),
            len(title_risk.risky_titles),
        )

        safe_title_set = set(title_risk.safe_titles)
        safe_titles = [t for t in titles if t.title in safe_title_set]
        if not safe_titles:
            warnings.append("No safe titles found; fallback to all titles.")
            safe_titles = titles

        logger.info("Selecting final title")
        selection, warning = self.title_optimizer.select_title(safe_titles, article)
        warnings.extend(warning)
        logger.info("Final title selected: %s", selection.final_title)

        draft_article = self.formatter.apply_title(article, selection.final_title)
        logger.info("Draft formatted with title")

        logger.info("Reviewing article quality")
        reviewed_article = draft_article
        auto_rewrite_performed = False
        review_round = 0
        review = None

        while True:
            review_round += 1
            review, warning = self.review_agent.review(
                final_title=selection.final_title,
                article_markdown=reviewed_article,
                fact_extract=fact_extract,
                title_risk=title_risk,
                raw_text=search_result.raw_text,
            )
            warnings.extend(warning)
            logger.info(
                "Review round %d done. score=%d, passed=%s, rewrite_required=%s",
                review_round,
                review.score,
                review.passed,
                review.rewrite_required,
            )
            if review.problems:
                logger.info("Review problems: %s", "; ".join(review.problems))
            if review.hallucination_risks:
                logger.info(
                    "Review hallucination risks: %s",
                    "; ".join(review.hallucination_risks),
                )

            if not review.rewrite_required:
                break
            if review_round >= MAX_REVIEW_ROUNDS:
                warnings.append(
                    "Max review rounds reached; using latest draft for final output."
                )
                break

            logger.info("Auto rewrite started (round %d)", review_round)
            rewritten, warning = self.review_agent.rewrite(
                final_title=selection.final_title,
                article_markdown=reviewed_article,
                review=review,
                fact_extract=fact_extract,
                raw_text=search_result.raw_text,
            )
            warnings.extend(warning)
            reviewed_article = rewritten
            auto_rewrite_performed = True
            logger.info(
                "Auto rewrite done. cjk_chars=%d, preview=%s",
                count_cjk_chars(reviewed_article),
                self._preview_text(reviewed_article),
            )

        logger.info("Final polish started")
        polished_article, warning = self.polish_agent.polish(
            final_title=selection.final_title,
            article_markdown=reviewed_article,
            fact_extract=fact_extract,
        )
        warnings.extend(warning)
        polished_article = self._strip_fact_tags(polished_article)

        final_article = self.formatter.apply_title(polished_article, selection.final_title)
        final_article = self._append_source_url(final_article, search_result.items)
        logger.info("Final article formatted")

        logger.info("Generating cover prompt")
        cover_prompt, warning = self.cover_prompt_generator.generate(
            selection.final_title, final_article
        )
        warnings.extend(warning)
        logger.info("Cover prompt ready. cover_text=%s", cover_prompt.cover_text)

        logger.info("Saving outputs")
        write_text(run_dir / "article.md", draft_article)
        write_text(run_dir / "final_article.md", final_article)
        write_json(run_dir / "fact_extract.json", fact_extract.model_dump())
        write_json(run_dir / "title_risk.json", title_risk.model_dump())
        write_json(run_dir / "review.json", review.model_dump())
        write_json(
            run_dir / "titles.json",
            {
                "titles": [t.model_dump() for t in titles],
                "final": selection.model_dump(),
            },
        )
        write_text(run_dir / "cover_prompt.md", cover_prompt.to_markdown())

        word_count = count_cjk_chars(final_article)
        human_check_required = review.human_check_required
        report = RunReport(
            run_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            created_at=datetime.now().isoformat(timespec="seconds"),
            search_provider=search_result.provider,
            draft_provider=self.llm_client.model,
            polish_provider=self.llm_client.model,
            selected_news_title=selected.title,
            final_title=selection.final_title,
            article_word_count=word_count,
            output_dir=str(run_dir),
            warnings=warnings,
            fact_count=len(fact_extract.verified_facts),
            number_count=len(fact_extract.verified_numbers),
            quote_count=len(fact_extract.verified_quotes),
            review_score=review.score if review else 0,
            review_passed=review.passed if review else False,
            final_review_passed=review.passed if review else False,
            unsupported_claims=review.unsupported_claims if review else [],
            title_risk_count=len(title_risk.risky_titles),
            auto_rewrite_performed=auto_rewrite_performed,
            human_check_required=human_check_required,
        )
        write_text(run_dir / "report.md", self._build_report_markdown(report))

        logger.info("Run completed: %s", run_dir)
        return run_dir

    def _preview_text(self, text: str, max_len: int = 160) -> str:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            return ""
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[:max_len].rstrip() + "..."

    def _strip_fact_tags(self, text: str) -> str:
        if not text:
            return ""
        cleaned = text.replace("【事实】", "").replace("【推断】", "")
        cleaned = cleaned.replace("【观点】", "").replace("【结论】", "")
        return cleaned

    @staticmethod
    def _append_source_url(article: str, news_items: List[NewsItem]) -> str:
        article = Workflow._strip_existing_reference_section(article)

        valid = [
            item for item in news_items
            if item.source and item.source.strip()
            and item.source.strip() not in ("用户提供", "网络来源", "未知来源")
        ]
        if not valid:
            return article

        seen_sources: set = set()
        ref_lines = ["", "", "---", REFERENCE_SECTION_HEADER]
        for item in valid:
            source = item.source.strip()
            if source in seen_sources:
                continue
            seen_sources.add(source)
            url = item.url.strip() if item.url else ""
            if url and url != "manual://" and not any(
                placeholder in url.lower() for placeholder in PLACEHOLDER_URL_MARKERS
            ):
                ref_lines.append(f"- [{source}]({url})")
            else:
                ref_lines.append(f"- {source}")

        return article + "\n".join(ref_lines)

    @staticmethod
    def _strip_existing_reference_section(article: str) -> str:
        """Remove any trailing reference block so the workflow can append one canonical copy."""
        if not article:
            return ""

        pattern = re.compile(
            r"\n{2,}---\n?\s*\*\*参考来源：\*\*.*$",
            re.DOTALL,
        )
        cleaned = pattern.sub("", article).rstrip()
        return cleaned

    def _build_report_markdown(self, report: RunReport) -> str:
        lines = [
            "# Run Report",
            "",
            f"- run_id: {report.run_id}",
            f"- created_at: {report.created_at}",
            f"- search_provider: {report.search_provider}",
            f"- draft_provider: {report.draft_provider}",
            f"- polish_provider: {report.polish_provider}",
            f"- selected_news_title: {report.selected_news_title}",
            f"- final_title: {report.final_title}",
            f"- article_word_count: {report.article_word_count}",
            f"- output_dir: {report.output_dir}",
            f"- fact_count: {report.fact_count}",
            f"- number_count: {report.number_count}",
            f"- quote_count: {report.quote_count}",
            f"- review_score: {report.review_score}",
            f"- review_passed: {report.review_passed}",
            f"- final_review_passed: {report.final_review_passed}",
            f"- title_risk_count: {report.title_risk_count}",
            f"- auto_rewrite_performed: {report.auto_rewrite_performed}",
            f"- human_check_required: {report.human_check_required}",
        ]
        if report.unsupported_claims:
            for claim in report.unsupported_claims:
                lines.append(f"- unsupported_claim: {claim}")
        if report.warnings:
            for warning in report.warnings:
                lines.append(f"- warning: {warning}")
        return "\n".join(lines) + "\n"
