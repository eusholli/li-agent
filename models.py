#!/usr/bin/env python3
"""Shared data models for LinkedIn Article Generator."""

from typing import List, Optional
from pydantic import BaseModel, Field


class FactCheckResult(BaseModel):
    """Results of fact-checking an article."""
    total_claims_found: int = Field(..., description="Total number of factual claims identified")
    claims_with_citations: int = Field(..., description="Number of claims that already have citations")
    valid_citations: int = Field(..., description="Number of citations that are valid")
    invalid_citations: int = Field(..., description="Number of citations that are invalid")
    uncited_claims: int = Field(..., description="Number of factual claims without citations")
    fact_check_passed: bool = Field(..., description="Whether the article passes fact-checking")
    improvement_needed: bool = Field(..., description="Whether improvements are needed")
    summary_feedback: str = Field(..., description="Summary of fact-checking results")
    detailed_feedback: str = Field(..., description="Detailed feedback with specific actions needed")
