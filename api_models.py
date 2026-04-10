"""Pydantic request/response models for the LinkedIn Article Generator API."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional

from li_article_judge import ARTICLE_TYPES


class GenerateRequest(BaseModel):
    """Request body for POST /articles/generate."""

    draft: str = Field(..., min_length=50, description="Article draft or outline text")
    article_type: str = Field(
        "thought_leadership",
        description=(
            "Type of LinkedIn article to generate. Controls scoring criteria and content style. "
            "Valid values: thought_leadership, awareness, demand_gen, event_attendance, "
            "recruitment, product_announcement, case_study"
        ),
    )

    @field_validator("article_type")
    @classmethod
    def validate_article_type(cls, v: str) -> str:
        if v not in ARTICLE_TYPES:
            raise ValueError(
                f"Invalid article_type {v!r}. Must be one of: {', '.join(ARTICLE_TYPES)}"
            )
        return v
    target_score: float = Field(
        89.0, ge=0.0, le=100.0, description="Target quality score percentage (used in scoring criteria prompt)"
    )
    max_iterations: int = Field(
        1, ge=1, le=1, description="Kept for backwards compat; always 1 (single-pass)"
    )
    word_count_min: int = Field(1500, ge=100, description="Minimum target word count")
    word_count_max: int = Field(2000, ge=100, description="Maximum target word count")
    model: str = Field(
        "gemini/gemini-2.5-flash",
        description="Default fallback model",
    )
    generator_model: Optional[str] = Field(
        "gemini/gemini-2.5-pro",
        description="Model for article generation (overrides model)",
    )
    judge_model: Optional[str] = Field(
        "gemini/gemini-2.5-flash",
        description="Model for fact-checking (overrides model)",
    )
    rag_model: Optional[str] = Field(
        "gemini/gemini-2.5-flash",
        description="Model for search query generation (overrides model)",
    )
    fact_check: bool = Field(
        True,
        description="Whether to fact-check the article against RAG sources",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "draft": "AI is transforming how businesses operate...",
                "word_count_min": 1500,
                "word_count_max": 2000,
            }
        }
    }


class HumanizeRequest(BaseModel):
    """Request body for POST /humanize."""

    article: str = Field(..., min_length=50, description="Article text to humanize")
    model: str = Field(
        "gemini/gemini-2.5-flash",
        description="Default fallback model",
    )
    humanizer_model: Optional[str] = Field(
        None,
        description="Override model for humanization (overrides model)",
    )
    use_undetectable: bool = Field(
        False,
        description="Whether to also run through Undetectable.ai API (requires UNDETECTABLE_API_KEY)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "article": "# Why AI Strategy Must Start at the Board Level\n\nMost executives think AI will automate their workforce...",
            }
        }
    }
