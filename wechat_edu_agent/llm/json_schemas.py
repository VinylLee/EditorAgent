from __future__ import annotations

NEWS_SELECT_SCHEMA = {
    "name": "news_selection",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "selected_news": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "news_type": {"type": "string"},
                    "title": {"type": "string"},
                    "source": {"type": "string"},
                    "published_at": {"type": "string"},
                    "url": {"type": "string"},
                    "summary": {"type": "string"},
                    "core_facts": {"type": "array", "items": {"type": "string"}},
                    "parent_emotion_points": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "relevance_score": {"type": "integer"},
                    "virality_score": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "news_type",
                    "title",
                    "source",
                    "published_at",
                    "url",
                    "summary",
                    "core_facts",
                    "parent_emotion_points",
                    "relevance_score",
                    "virality_score",
                    "reason",
                ],
            },
            "reason": {"type": "string"},
            "parent_emotion_points": {"type": "array", "items": {"type": "string"}},
            "deep_logic_angles": {"type": "array", "items": {"type": "string"}},
            "suggested_article_angle": {"type": "string"},
            "risk_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "selected_news",
            "reason",
            "parent_emotion_points",
            "deep_logic_angles",
            "suggested_article_angle",
            "risk_notes",
        ],
    },
}

TITLE_GEN_SCHEMA = {
    "name": "title_generation",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "titles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "reason": {"type": "string"},
                        "risk": {"type": "string"},
                    },
                    "required": ["title", "score", "reason", "risk"],
                },
            }
        },
        "required": ["titles"],
    },
}

TITLE_SELECT_SCHEMA = {
    "name": "title_selection",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "final_title": {"type": "string"},
            "why_selected": {"type": "string"},
            "optimized_reason": {"type": "string"},
        },
        "required": ["final_title", "why_selected", "optimized_reason"],
    },
}

COVER_PROMPT_SCHEMA = {
    "name": "cover_prompt",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "cover_prompt_cn": {"type": "string"},
            "cover_prompt_en": {"type": "string"},
            "negative_prompt": {"type": "string"},
            "suggested_layout": {"type": "string"},
            "cover_text": {"type": "string"},
        },
        "required": [
            "cover_prompt_cn",
            "cover_prompt_en",
            "negative_prompt",
            "suggested_layout",
            "cover_text",
        ],
    },
}

REVIEW_SCHEMA = {
    "name": "article_review",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "passed": {"type": "boolean"},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "rewrite_required": {"type": "boolean"},
            "problems": {"type": "array", "items": {"type": "string"}},
            "hallucination_risks": {
                "type": "array",
                "items": {"type": "string"},
            },
            "unsupported_claims": {
                "type": "array",
                "items": {"type": "string"},
            },
            "title_risks": {"type": "array", "items": {"type": "string"}},
            "rewrite_instructions": {"type": "string"},
            "human_check_required": {"type": "boolean"},
        },
        "required": [
            "passed",
            "score",
            "rewrite_required",
            "problems",
            "hallucination_risks",
            "unsupported_claims",
            "title_risks",
            "rewrite_instructions",
            "human_check_required",
        ],
    },
}

FACT_EXTRACT_SCHEMA = {
    "name": "fact_extract",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "verified_facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "fact": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["id", "fact", "evidence"],
                },
            },
            "verified_numbers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "number": {"type": "string"},
                        "meaning": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["id", "number", "meaning", "evidence"],
                },
            },
            "verified_quotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "quote": {"type": "string"},
                        "speaker": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["id", "quote", "speaker", "evidence"],
                },
            },
            "allowed_inferences": {"type": "array", "items": {"type": "string"}},
            "forbidden_claims": {"type": "array", "items": {"type": "string"}},
            "uncertain_points": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "verified_facts",
            "verified_numbers",
            "verified_quotes",
            "allowed_inferences",
            "forbidden_claims",
            "uncertain_points",
        ],
    },
}

TITLE_RISK_SCHEMA = {
    "name": "title_risk",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "safe_titles": {"type": "array", "items": {"type": "string"}},
            "risky_titles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "risk_level": {"type": "string"},
                        "reason": {"type": "string"},
                        "suggested_fix": {"type": "string"},
                    },
                    "required": [
                        "title",
                        "risk_level",
                        "reason",
                        "suggested_fix",
                    ],
                },
            },
            "recommended_title": {"type": "string"},
        },
        "required": ["safe_titles", "risky_titles", "recommended_title"],
    },
}
