#!/usr/bin/env python3
"""
LinkedIn Article Generator - Single-pass pipeline.

Pipeline: RAG search -> generate article -> humanize -> optional fact-check
"""

import asyncio
import logging
import re
from typing import Any, Callable, Dict, Optional, Tuple

import dspy

from dspy_factory import DspyModelConfig
from li_article_judge import CriteriaExtractor
from rag_fast import retrieve_and_pack
from humanizer import humanize_article

logging.basicConfig(level=logging.WARNING)


# ---------------------------------------------------------------------------
# DSPy Signature for article generation
# ---------------------------------------------------------------------------

class ArticleGenerationSignature(dspy.Signature):
    """Generate a complete LinkedIn article in markdown format with these requirements:

    WORD LENGTH REQUIREMENT:
    - The top priority is to generate an article of the wanted length range
    - If expansion is needed, focus on areas that improve both length and quality
    - Use the scoring criteria to strategically adjust content length

    MARKDOWN FORMATTING:
    - Use clear header hierarchy (# ## ###)
    - Include bullet points and numbered lists where appropriate
    - Use **bold** and *italic* emphasis for key points
    - Professional paragraph structure with engaging subheadings

    CITATION CREATION:
    - The context string contains inline citations as [specific claim](source_url)
    - Use these pre-formatted citations directly when incorporating relevant information
    - ONLY cite information that directly appears in the provided context
    - Present analysis, opinions, and synthesis as uncited content

    CONTENT REQUIREMENTS:
    - Expand the draft/outline into a comprehensive LinkedIn article
    - Maintain professional LinkedIn tone and structure
    - Objective and third-person, with a structured, business/technical tone
    - Address all key points from the original draft"""

    original_draft: str = dspy.InputField(desc="Original draft to expand")
    context: str = dspy.InputField(
        desc="Web research context with inline citations as [text](url)", default=""
    )
    scoring_criteria: str = dspy.InputField(desc="Scoring criteria for quality optimization")
    generated_article: str = dspy.OutputField(desc="The generated LinkedIn article in markdown")


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[str, str], None]


def _noop_progress(stage: str, message: str) -> None:
    pass


class LinkedInArticleGenerator:
    """
    Single-pass LinkedIn article generator.

    Pipeline:
      1. RAG web search for supporting context
      2. Generate article with scoring criteria in prompt
      3. Humanize (single LLM pass)
      4. Optional: fact-check against sources
    """

    def __init__(
        self,
        models: Dict[str, DspyModelConfig],
        word_count_min: int = 2000,
        word_count_max: int = 2500,
        on_progress: Optional[ProgressCallback] = None,
        fact_check: bool = True,
        use_undetectable: bool = False,
    ):
        self.models = models
        self.word_count_min = word_count_min
        self.word_count_max = word_count_max
        self.progress = on_progress or _noop_progress
        self.fact_check = fact_check
        self.use_undetectable = use_undetectable

        self.criteria_extractor = CriteriaExtractor(word_count_min, word_count_max)
        self.generator = dspy.ChainOfThought(ArticleGenerationSignature)

    def generate_article(self, draft: str) -> Dict[str, Any]:
        """
        Generate a LinkedIn article from a draft.

        Args:
            draft: Article draft or outline text

        Returns:
            Dict with keys: original_article, humanized_article, word_count,
                           fact_check_result (optional), context_urls
        """
        self.progress("start", "Starting article generation")

        # 1. RAG search
        self.progress("rag_search", "Searching the web for supporting context...")
        context, urls = asyncio.run(
            retrieve_and_pack(
                draft,
                models=self.models,
                on_progress=self.progress,
            )
        )

        # 2. Generate article
        self.progress("generating", "Generating article...")
        scoring_criteria = self.criteria_extractor.get_criteria_for_generation()

        with dspy.context(lm=self.models["generator"].dspy_lm):
            result = self.generator(
                original_draft=draft,
                context=context,
                scoring_criteria=scoring_criteria,
            )

        article = result.generated_article
        word_count = len(re.sub(r"\s+", " ", article.strip()).split())

        self.progress(
            "generated",
            f"Article generated - {word_count} words",
        )

        # 3. Optional fact-check
        fact_check_result = None
        if self.fact_check and context:
            self.progress("fact_checking", "Fact-checking the article against sources...")
            try:
                article, fact_check_result = self._fact_check(article, context)
                status = "passed" if fact_check_result.fact_check_passed else "needs revision"
                self.progress(
                    "fact_check_results",
                    f"Fact-check {status}: {fact_check_result.summary_feedback}",
                )
            except Exception as e:
                logging.error(f"Fact-checking failed: {e}")
                self.progress("fact_check_results", f"Fact-check skipped: {e}")

        # 4. Humanize
        humanizer_cfg = self.models.get("humanizer") or self.models["generator"]
        with dspy.context(lm=humanizer_cfg.dspy_lm):
            humanized = humanize_article(
                article,
                on_progress=self.progress,
                use_undetectable=self.use_undetectable,
            )

        self.progress("complete_generation", "Article generation complete")

        return {
            "original_article": article,
            "humanized_article": humanized,
            "word_count": word_count,
            "fact_check_result": fact_check_result,
            "context_urls": urls,
        }

    def _fact_check(self, article: str, context: str):
        """Run fact-checker and return (possibly revised article, result)."""
        from fc_oc_v2 import FactChecker

        checker = FactChecker(self.models)
        with dspy.context(lm=self.models["judge"].dspy_lm):
            prediction = checker(article, context)

        output = prediction.output
        revised = output.revised_article if not output.fact_check_passed else article
        return revised, output
