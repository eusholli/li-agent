"""Pydantic request/response models for the LinkedIn Article Generator API."""

from pydantic import BaseModel, Field
from typing import Optional


class GenerateRequest(BaseModel):
    """Request body for POST /articles/generate."""

    draft: str = Field(..., min_length=50, description="Article draft or outline text")
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
    use_undetectable: bool = Field(
        False,
        description="Whether to run through Undetectable.ai API (requires UNDETECTABLE_API_KEY)",
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
