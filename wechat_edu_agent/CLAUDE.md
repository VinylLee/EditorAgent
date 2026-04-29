# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WeChat public account ("教育最前沿") automated content generation agent. Takes manually-input news, generates a WeChat article with titles, cover image prompts, fact-extraction, risk assessment, and quality review — all via OpenAI-compatible LLMs.

## Commands

```bash
# Run the full pipeline with manual news input
python main.py run --manual-news ./news/sample_news.txt

# With optional topic and news type
python main.py run --manual-news ./news/sample_news.txt --topic "减负 内卷" --news-type "社会事件"

# Activate conda environment
conda activate agent311
```

No tests, linter, or formatter are configured.

## Architecture

### Pipeline (agents/workflow.py)

The `Workflow.run()` orchestrates these steps in order:

1. **Search** — `SearchProvider` (abstract; only `ManualNewsProvider` implemented) reads a text file and wraps it as a `SearchResult`
2. **News Selection** (`NewsSelector`) — LLM picks the best news item and suggests an article angle
3. **Fact Extraction** (`FactExtractAgent`) — LLM extracts verified facts/numbers/quotes from raw text, plus allowed inferences and forbidden claims
4. **Article Writing** (`ArticleWriter`) — LLM generates a ~1200-1800 CJK-character draft with `【事实】`/`【推断】` markers
5. **Title Generation** (`TitleOptimizer`) — LLM generates 10 candidate titles with scores
6. **Title Risk Assessment** (`TitleRiskAgent`) — LLM classifies titles as safe or risky; only safe titles proceed
7. **Title Selection** (`TitleOptimizer.select_title`) — LLM picks the final title from safe candidates
8. **Review → Rewrite Loop** (`ReviewAgent`) — quality check; up to 3 rounds of auto-rewrite if `rewrite_required=true`. Hard rules: hallucination risks → fail, unsupported claims → fail, high-risk titles → fail, score < 85 → fail, word count out of range → rewrite
9. **Final Polish** (`PolishAgent`) — removes `【事实】`/`【推断】` tags, final formatting
10. **Cover Prompt Generation** (`CoverPromptGenerator`) — LLM generates Chinese and English cover image prompts
11. **Output** — writes article.md, final_article.md, fact_extract.json, titles.json, title_risk.json, review.json, cover_prompt.md, report.md, llm_trace.jsonl into `outputs/YYYYMMDD_HHMM_<slug>/`

### Key Design Decisions

- **Search is pluggable** via `SearchProvider` ABC in `search/base.py`. Currently only `ManualNewsProvider` exists (reads a local text file). The design supports adding DashScope/Gemini/custom search providers.
- **LLM client** (`llm/client.py`) wraps `openai.OpenAI` and supports three JSON modes via `LLM_JSON_MODE` env var: `off` (free text), `json_object` (forces JSON output), `json_schema` (structured output with schema). All LLM calls are traced to `llm_trace.jsonl`.
- **JSON repair** — every agent that expects JSON from the LLM has a fallback repair mechanism: it feeds the raw output back to the LLM asking for JSON-only reformatting.
- **All agents return `Tuple[Result, List[str]]`** — the first element is the structured result, the second is a list of warnings/errors.
- **Configuration** from `.env` via `python-dotenv`, loaded into a `dataclass` in `config.py`. Supports fallback env vars (e.g., `LLM_BASE_URL` ← `LMSTUDIO_BASE_URL` ← `DEEPSEEK_BASE_URL`).

### Key Files

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point, arg parsing |
| `config.py` | `.env` → `AppConfig` dataclass |
| `llm/client.py` | OpenAI wrapper with tracing and JSON mode support |
| `llm/prompts.py` | All system prompts (Chinese) |
| `llm/json_schemas.py` | JSON schemas for structured output mode |
| `models/schemas.py` | All Pydantic models (NewsItem, ReviewResult, FactExtractResult, etc.) |
| `agents/workflow.py` | Pipeline orchestration |
| `search/base.py` | `SearchProvider` abstract base |
| `utils/json_utils.py` | LLM JSON output extraction/repair |
| `utils/text_utils.py` | CJK char counting, slugify |
| `utils/file_utils.py` | Output directory creation, file writing |

### Important Conventions

- All agents accept `llm_client` as a constructor dependency (no separate abstract base per agent).
- Agent methods always return `(result, warnings: List[str])`.
- All `chat_json` calls use `safe_json_loads` from `utils.json_utils` to extract JSON from potentially malformed LLM output.
- Fact extraction output is the single source of truth — article writing and review both reference it to prevent hallucination.
- Output directory naming: `outputs/{YYYYMMDD_HHMM}_{slugified_topic}/`.
