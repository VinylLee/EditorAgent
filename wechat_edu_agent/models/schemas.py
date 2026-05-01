from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    news_type: str
    title: str
    source: str
    published_at: str
    url: str
    summary: str
    core_facts: List[str] = Field(default_factory=list)
    parent_emotion_points: List[str] = Field(default_factory=list)
    relevance_score: int = 0
    virality_score: int = 0
    reason: str = ""


class TitleCandidate(BaseModel):
    title: str
    score: int
    reason: str
    risk: str


class TitleSelection(BaseModel):
    final_title: str
    why_selected: str
    optimized_reason: str


class NewsSelectionResult(BaseModel):
    selected_news: NewsItem
    reason: str = ""
    parent_emotion_points: List[str] = Field(default_factory=list)
    deep_logic_angles: List[str] = Field(default_factory=list)
    suggested_article_angle: str = ""
    risk_notes: List[str] = Field(default_factory=list)


class CoverPrompt(BaseModel):
    cover_prompt_cn: str
    cover_prompt_en: str
    negative_prompt: str
    suggested_layout: str
    cover_text: str

    def to_markdown(self) -> str:
        lines = [
            "# Cover Prompt",
            "",
            f"cover_prompt_cn: {self.cover_prompt_cn}",
            f"cover_prompt_en: {self.cover_prompt_en}",
            f"negative_prompt: {self.negative_prompt}",
            f"suggested_layout: {self.suggested_layout}",
            f"cover_text: {self.cover_text}",
        ]
        return "\n".join(lines) + "\n"


class FactRecord(BaseModel):
    id: str
    fact: str
    evidence: str


class NumberRecord(BaseModel):
    id: str
    number: str
    meaning: str
    evidence: str


class QuoteRecord(BaseModel):
    id: str
    quote: str
    speaker: str
    evidence: str


class FactExtractResult(BaseModel):
    verified_facts: List[FactRecord] = Field(default_factory=list)
    verified_numbers: List[NumberRecord] = Field(default_factory=list)
    verified_quotes: List[QuoteRecord] = Field(default_factory=list)
    allowed_inferences: List[str] = Field(default_factory=list)
    forbidden_claims: List[str] = Field(default_factory=list)
    uncertain_points: List[str] = Field(default_factory=list)


class TitleRiskItem(BaseModel):
    title: str
    risk_level: str
    reason: str
    suggested_fix: str


class TitleRiskResult(BaseModel):
    safe_titles: List[str] = Field(default_factory=list)
    risky_titles: List[TitleRiskItem] = Field(default_factory=list)
    recommended_title: str = ""


class ReviewResult(BaseModel):
    passed: bool = False
    score: int = 0
    rewrite_required: bool = False
    problems: List[str] = Field(default_factory=list)
    hallucination_risks: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    title_risks: List[str] = Field(default_factory=list)
    rewrite_instructions: str = ""
    human_check_required: bool = True


class SearchResult(BaseModel):
    items: List[NewsItem] = Field(default_factory=list)
    raw_text: str = ""
    provider: str = "manual"


class RunReport(BaseModel):
    run_id: str
    created_at: str
    search_provider: str
    draft_provider: str
    polish_provider: str
    selected_news_title: str
    final_title: str
    article_word_count: int
    output_dir: str
    warnings: List[str] = Field(default_factory=list)
    fact_count: int = 0
    number_count: int = 0
    quote_count: int = 0
    review_score: int = 0
    review_passed: bool = False
    final_review_passed: bool = False
    unsupported_claims: List[str] = Field(default_factory=list)
    title_risk_count: int = 0
    auto_rewrite_performed: bool = False
    human_check_required: bool = False
    dedup_enabled: bool = False
    dedup_removed_count: int = 0
    dedup_history_size: int = 0
    dedup_similarity_threshold: float = 0.0
    dedup_title_threshold: float = 0.0
    dedup_recent_days: int = 0
