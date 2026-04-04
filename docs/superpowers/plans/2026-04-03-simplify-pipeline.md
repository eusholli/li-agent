# Simplify LinkedIn Article Generator Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the article generation pipeline from 6+ LLM calls / ~240s to 3 LLM calls / ~100s by removing the unused iterative improvement loop, simplifying RAG, merging humanizer passes, and making fact-checking/Undetectable.ai opt-in.

**Architecture:** Single-pass pipeline: RAG topic extraction (1 LLM) -> web search (Tavily basic) -> article generation with scoring criteria in prompt (1 LLM) -> humanize in single pass (1 LLM) -> optional fact-check (1 LLM) -> optional Undetectable.ai API. Progress reporting via simple callback function instead of OutputManager class hierarchy.

**Tech Stack:** Python 3.9+, DSPy 3.1.3, FastAPI, Tavily, Pydantic, SSE-starlette

---

## File Structure

### Files to Rewrite (major changes):
- `linkedin_article_generator.py` — Single-pass generator with callback-based progress
- `rag_fast.py` — Simplified RAG: basic search, use snippets, skip full-page extraction
- `humanizer.py` — Single LLM pass combining AI-pattern removal + brand voice
- `main.py` — Simple CLI, no parallel versions, no MLflow, no interactive menu
- `api.py` — Updated for simplified generator, callback-based progress

### Files to Simplify (keep partial content):
- `li_article_judge.py` — Keep only `SCORING_CRITERIA` dict and `CriteriaExtractor` class. Remove all scoring modules.
- `models.py` — Keep `FactCheckResult` only. Remove `JudgementModel`, `ArticleVersion`, `ScoreResultModel`, `ArticleScoreModel`.
- `api_models.py` — Remove unused fields (`recreate_ctx`, `humanizer_model`)

### Files to Keep As-Is:
- `dspy_factory.py` — Works correctly
- `gemini_factory.py` — Works correctly
- `model_cache.py` — Works correctly
- `auth.py` — Works correctly
- `fc_oc_v2.py` — `FactChecker` class is already single-call, works correctly

### Files to Delete:
- `context_window_manager.py` — Over-engineered token budget; replaced by simple truncation
- `word_count_manager.py` — 615 lines; replaced by inline `len(text.split())`
- `progress_dashboard.py` — Unused in simplified flow
- `output_manager.py` — Replaced by callback pattern

---

## Tasks

### Task 1: Simplify `models.py`

**Files:**
- Modify: `models.py`

- [ ] **Step 1: Rewrite models.py to keep only what's needed**

The simplified pipeline doesn't use `JudgementModel`, `ArticleVersion`, or `ArticleScoreModel`. Keep only `FactCheckResult` (used by `fc_oc_v2.py`).

```python
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
```

- [ ] **Step 2: Verify no import breaks**

Run: `python -c "from models import FactCheckResult; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add models.py
git commit -m "simplify: strip models.py to FactCheckResult only"
```

---

### Task 2: Simplify `li_article_judge.py` to criteria-only module

**Files:**
- Modify: `li_article_judge.py`

- [ ] **Step 1: Rewrite li_article_judge.py keeping only SCORING_CRITERIA and CriteriaExtractor**

Remove all DSPy scoring modules (`LinkedInArticleScorer`, `FastLinkedInArticleScorer`, `ComprehensiveLinkedInArticleJudge`, `ABArticleScorer`, etc.), all Pydantic scoring output models, and the CLI. Keep the `SCORING_CRITERIA` dict and the `CriteriaExtractor` class (used by the generation prompt).

```python
#!/usr/bin/env python3
"""
LinkedIn Article Scoring Criteria

Contains the scoring criteria definitions and CriteriaExtractor for generating
scoring-aware prompts. No LLM scoring is performed here — the criteria are
embedded into the generation prompt so the LLM optimizes for them directly.
"""

from typing import Dict, List, Tuple, Optional
from models import FactCheckResult  # noqa: keep for fc_oc_v2 compatibility

# ==========================================================================
# SCORING CRITERIA DEFINITIONS (180 points total)
# ==========================================================================

SCORING_CRITERIA = {
    "First-Order Thinking": [
        {
            "question": "Does the article break down complex problems into fundamental components rather than relying on analogies or existing solutions?",
            "points": 15,
            "scale": {
                1: "Relies heavily on analogies and surface-level comparisons",
                3: "Some attempt to examine fundamentals but inconsistent",
                5: "Consistently breaks problems down to basic principles and rebuilds understanding",
            },
        },
        {
            "question": "Does it challenge conventional wisdom by examining root assumptions and rebuilding from basic principles?",
            "points": 15,
            "scale": {
                1: "Accepts conventional wisdom without question",
                3: "Questions some assumptions but doesn't dig deep",
                5: "Systematically challenges assumptions and rebuilds from first principles",
            },
        },
        {
            "question": "Does it avoid surface-level thinking and instead dig into the 'why' behind commonly accepted ideas?",
            "points": 15,
            "scale": {
                1: "Stays at surface level with obvious observations",
                3: "Some deeper analysis but not consistently applied",
                5: "Consistently probes deeper into root causes and fundamental 'why' questions",
            },
        },
    ],
    "Strategic Deconstruction & Synthesis": [
        {
            "question": "Does it deconstruct a complex system (a market, a company's strategy, a technology) into its fundamental components and incentives?",
            "points": 20,
            "scale": {
                1: "Describes the system at a surface level without dissecting it.",
                3: "Identifies some components but doesn't fully explain their interactions or underlying incentives.",
                5: "Systematically breaks down the system into its core parts and clearly explains how they interact.",
            },
        },
        {
            "question": "Does it synthesize disparate information (e.g., history, financial data, product strategy, quotes) into a single, coherent thesis?",
            "points": 20,
            "scale": {
                1: "Presents information as a list of disconnected facts.",
                3: "Attempts to connect different pieces of information, but the central thesis is weak or unclear.",
                5: "Masterfully weaves together diverse sources into a strong, unified, and memorable argument.",
            },
        },
        {
            "question": "Does it identify second- and third-order effects, explaining the cascading 'so what?' consequences of a core idea or event?",
            "points": 15,
            "scale": {
                1: "Focuses only on the immediate, first-order effects.",
                3: "Mentions some downstream effects but doesn't explore their full implications.",
                5: "Clearly explains the chain reaction of consequences, showing deep understanding of the system's dynamics.",
            },
        },
        {
            "question": "Does it introduce a durable framework or mental model that helps explain the system and is transferable to other contexts?",
            "points": 15,
            "scale": {
                1: "Offers opinions without a clear underlying framework.",
                3: "Uses existing frameworks but doesn't introduce a new or refined mental model.",
                5: "Provides a powerful, memorable, and reusable mental model for understanding the topic.",
            },
        },
        {
            "question": "Does it explain the fundamental 'why' behind events, rather than just describing the 'what'?",
            "points": 5,
            "scale": {
                1: "Reports on events without providing deep causal analysis.",
                3: "Offers some explanation for the 'why' but it remains at a surface level.",
                5: "Consistently digs beneath the surface to reveal the core strategic, economic, or historical drivers.",
            },
        },
    ],
    "Hook & Engagement": [
        {
            "question": "Does the opening immediately grab attention with curiosity, emotion, or urgency?",
            "points": 5,
            "scale": {
                1: "Bland opening; no reason to keep reading",
                3: "Somewhat interesting but predictable",
                5: "Strong hook that makes reading irresistible",
            },
        },
        {
            "question": "Does the intro clearly state why this matters to the reader in the first 3 sentences?",
            "points": 5,
            "scale": {
                1: "Relevance is unclear",
                3: "Relevance implied but not explicit",
                5: "Clear, personal relevance to target audience immediately",
            },
        },
    ],
    "Storytelling & Structure": [
        {
            "question": "Is the article structured like a narrative (problem -> tension -> resolution -> takeaway)?",
            "points": 5,
            "scale": {
                1: "Disjointed list of points",
                3: "Some flow, but transitions are weak",
                5: "Smooth arc with a natural flow that keeps readers moving",
            },
        },
        {
            "question": "Are there specific, relatable examples or anecdotes?",
            "points": 5,
            "scale": {
                1: "Generic statements with no real-life grounding",
                3: "Some examples, but not vivid",
                5: "Memorable examples that make points stick",
            },
        },
    ],
    "Authority & Credibility": [
        {
            "question": "Are claims backed by data, research, or credible sources?",
            "points": 5,
            "scale": {
                1: "No evidence given",
                3: "Some supporting info, but patchy",
                5: "Strong, credible evidence throughout",
            },
        },
        {
            "question": "Does the article demonstrate unique experience or perspective?",
            "points": 5,
            "scale": {
                1: "Generic, could be written by anyone",
                3: "Some personal insight but not distinct",
                5: "Clear, lived authority shines through",
            },
        },
    ],
    "Idea Density & Clarity": [
        {
            "question": "Is there one clear, central idea driving the piece?",
            "points": 5,
            "scale": {
                1: "Multiple competing ideas; scattered focus",
                3: "Mostly one theme but diluted by tangents",
                5: "Laser-focused on one strong idea",
            },
        },
        {
            "question": "Is every sentence valuable (no filler or fluff)?",
            "points": 5,
            "scale": {
                1: "Lots of repetition or empty words",
                3: "Mostly relevant with occasional filler",
                5: "Concise, high-value throughout",
            },
        },
    ],
    "Reader Value & Actionability": [
        {
            "question": "Does the reader walk away with practical, actionable insights?",
            "points": 5,
            "scale": {
                1: "Vague advice, nothing to act on",
                3: "Some useful tips but not clearly actionable",
                5: "Concrete steps or takeaways that can be applied immediately",
            },
        },
        {
            "question": "Are lessons transferable beyond the example given?",
            "points": 5,
            "scale": {
                1: "Only relevant in a narrow context",
                3: "Partially transferable",
                5: "Clearly relevant across multiple scenarios",
            },
        },
    ],
    "Call to Connection": [
        {
            "question": "Does it end with a thought-provoking question or reflection prompt?",
            "points": 5,
            "scale": {
                1: "No CTA or a generic 'What do you think?'",
                3: "Somewhat engaging but generic",
                5: "Strong, specific prompt that sparks dialogue",
            },
        },
        {
            "question": "Does it use inclusive, community-building language ('we,' 'us,' shared goals)?",
            "points": 5,
            "scale": {
                1: "Detached, academic tone",
                3: "Some warmth but not consistent",
                5: "Warm, inclusive tone throughout",
            },
        },
    ],
}


# ==========================================================================
# CRITERIA EXTRACTOR
# ==========================================================================


class CriteriaExtractor:
    """
    Extracts and formats scoring criteria for article generation prompts.
    The criteria are embedded in the generation prompt so the LLM optimizes
    for them directly — no separate scoring step needed.
    """

    def __init__(self, min_length: int, max_length: int):
        self.criteria = SCORING_CRITERIA
        self.min_length = min_length
        self.max_length = max_length
        self._category_weights: Optional[Dict[str, int]] = None

    def get_category_weights(self) -> Dict[str, int]:
        if self._category_weights is None:
            self._category_weights = {
                cat: sum(c.get("points", 5) for c in criteria)
                for cat, criteria in self.criteria.items()
            }
        return self._category_weights

    def get_total_possible_score(self) -> int:
        return sum(self.get_category_weights().values())

    def get_criteria_for_generation(self) -> str:
        """Format criteria for the article generation prompt."""
        lines = [
            "SCORING CRITERIA FOR ARTICLE GENERATION:",
            "Your article will be evaluated on these criteria:\n",
            f"**Article Length** (200 points total):",
            f"As the top priority the article must be between {self.min_length} and {self.max_length} words in length.",
            "",
        ]

        weights = self.get_category_weights()
        for category, total_points in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"**{category}** ({total_points} points total):")
            for criterion in self.criteria[category]:
                points = criterion.get("points", 5)
                lines.append(f"  * ({points} pts) {criterion['question']}")
                if points >= 15:
                    scale = criterion.get("scale", {})
                    if scale:
                        lines.append(f"    Scale: {scale.get(5, 'Excellent performance')}")
            lines.append("")

        lines.extend([
            "OPTIMIZATION PRIORITIES:",
            "1. Article length is most important (200 points)",
            "2. Focus heavily on Strategic Deconstruction & Synthesis (75 points)",
            "3. Emphasize First-Order Thinking (45 points)",
            "4. Ensure strong engagement and professional authority",
        ])

        return "\n".join(lines)
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from li_article_judge import SCORING_CRITERIA, CriteriaExtractor; print(f'OK: {len(SCORING_CRITERIA)} categories')"`
Expected: `OK: 8 categories`

- [ ] **Step 3: Commit**

```bash
git add li_article_judge.py
git commit -m "simplify: strip li_article_judge.py to criteria definitions only"
```

---

### Task 3: Simplify `rag_fast.py` — use search snippets, skip extraction

**Files:**
- Modify: `rag_fast.py`

- [ ] **Step 1: Rewrite rag_fast.py**

Key changes:
- Use "basic" search depth instead of "advanced"
- 3 results per query instead of 6
- Use search result snippets directly — skip the `_aextract()` full-page extraction entirely
- Remove the elaborate TextPacker; just format snippets with URLs
- Keep TopicExtractionSignature and caching
- Remove ContextWindowManager dependency

```python
"""
Fast web RAG retriever using Tavily search snippets.
- Fully async
- Uses search snippets directly (no full-page extraction)
- Thread-safe caching
- Returns a packed context string for the DSPy generation prompt
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import dspy
from pydantic import BaseModel, Field
from tavily import AsyncTavilyClient
from dotenv import load_dotenv

from dspy_factory import DspyModelConfig

logging.basicConfig(level=logging.WARNING)
load_dotenv()

# ---------------------------------------------------------------------------
# Cache (module-level, thread-safe)
# ---------------------------------------------------------------------------

_cache: Dict[str, Any] = {"searches": {}}
_cache_lock = asyncio.Lock()
_cache_initialized = False


def _load_cache(cache_file: str) -> None:
    global _cache_initialized, _cache
    if _cache_initialized:
        return
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                _cache.update(json.load(f))
    except Exception as e:
        logging.warning(f"Failed to load cache: {e}")
        _cache = {"searches": {}}
    _cache_initialized = True


def _save_cache(cache_file: str) -> None:
    try:
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(cache_file) or ".")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(_cache, f, indent=2, ensure_ascii=False)
            os.rename(temp_path, cache_file)
        except Exception:
            os.unlink(temp_path)
            raise
    except Exception as e:
        logging.warning(f"Failed to save cache: {e}")


# ---------------------------------------------------------------------------
# Topic extraction (1 LLM call)
# ---------------------------------------------------------------------------

class TopicExtractionResult(BaseModel):
    main_topic: str = Field(..., description="Main topic/subject of the article")
    search_queries: List[str] = Field(
        ...,
        description="Up to 3 optimized search queries to find supporting evidence and context",
    )
    needs_research: bool = Field(..., description="Whether this topic benefits from web research")


class TopicExtractionSignature(dspy.Signature):
    """Extract the main topic and generate search queries for supporting research."""
    draft_or_outline = dspy.InputField(desc="Article draft or outline to analyze")
    output: TopicExtractionResult = dspy.OutputField(
        desc="Main topic, search queries, and research needs flag"
    )


# ---------------------------------------------------------------------------
# Tavily search (snippets only, no extraction)
# ---------------------------------------------------------------------------

@dataclass
class TavilySettings:
    api_key: Optional[str] = None
    search_depth: str = "basic"
    max_results: int = 3
    timeout: int = 30
    cache_file: str = "tavily_cache.json"


async def _search_tavily(client: AsyncTavilyClient, query: str, settings: TavilySettings) -> dict:
    """Run a single Tavily search with caching."""
    async with _cache_lock:
        cached = _cache["searches"].get(query)
        if cached:
            return cached.get("response", {})

    response = await client.search(
        query=query,
        search_depth=settings.search_depth,
        max_results=settings.max_results,
        timeout=settings.timeout,
    )

    async with _cache_lock:
        _cache["searches"][query] = {"timestamp": time.time(), "response": response}
        await asyncio.to_thread(_save_cache, settings.cache_file)

    return response


def _pack_snippets(search_responses: List[dict], max_chars: int = 50_000) -> Tuple[str, List[str]]:
    """
    Pack search result snippets into a context string with inline citations.
    Format: [snippet text](url)
    """
    seen_urls = set()
    items: List[str] = []
    urls_used: List[str] = []
    total_chars = 0

    for resp in search_responses:
        if isinstance(resp, Exception):
            continue
        for result in resp.get("results", []):
            url = result.get("url", "")
            content = result.get("content", "")
            if not url or not content or url in seen_urls:
                continue
            seen_urls.add(url)

            # Format as inline citation
            citation = f"[{content.strip()}]({url})"
            citation_len = len(citation)
            if total_chars + citation_len > max_chars:
                break
            items.append(citation)
            urls_used.append(url)
            total_chars += citation_len

    return "\n\n".join(items), urls_used


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def retrieve_and_pack(
    draft_article: str,
    models: Dict[str, DspyModelConfig],
    on_progress=None,
    max_context_chars: int = 50_000,
) -> Tuple[str, List[str]]:
    """
    End-to-end RAG: extract topics -> search -> pack snippets.

    Args:
        draft_article: The draft text to research
        models: Model configs (needs "generator" for topic extraction)
        on_progress: Optional callback(stage, message) for progress reporting
        max_context_chars: Max characters for the packed context string

    Returns:
        (context_string, list_of_urls_used)
    """
    progress = on_progress or (lambda stage, msg: None)

    # 1. Extract search queries (1 LLM call)
    progress("info", "Analyzing draft to identify research topics...")
    topic_extractor = dspy.ChainOfThought(TopicExtractionSignature)
    with dspy.context(lm=models["generator"].dspy_lm):
        topic_results = topic_extractor(draft_or_outline=draft_article).output

    if not topic_results.needs_research:
        progress("info", "No research needed based on topic extraction.")
        return "", []

    queries = [topic_results.main_topic] + topic_results.search_queries[:2]  # main + up to 2 more
    progress("rag_queries", f"Search queries: {', '.join(queries)}")

    # 2. Search (async, cached)
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logging.warning("TAVILY_API_KEY not set, skipping RAG")
        return "", []

    settings = TavilySettings(api_key=api_key)
    _load_cache(settings.cache_file)
    client = AsyncTavilyClient(api_key)

    search_responses = await asyncio.gather(
        *[_search_tavily(client, q, settings) for q in queries],
        return_exceptions=True,
    )

    # 3. Pack snippets into context
    context, urls = _pack_snippets(search_responses, max_chars=max_context_chars)

    if context:
        url_count = len(urls)
        citation_count = context.count("](http")
        progress("rag_complete", f"Retrieved context from {url_count} source(s) ({citation_count} citations)")
    else:
        progress("info", "No relevant search results found.")

    return context, urls
```

- [ ] **Step 2: Verify module loads**

Run: `python -c "from rag_fast import retrieve_and_pack, TopicExtractionSignature; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add rag_fast.py
git commit -m "simplify: RAG uses search snippets only, skip full-page extraction"
```

---

### Task 4: Simplify `humanizer.py` — single LLM pass

**Files:**
- Modify: `humanizer.py`

- [ ] **Step 1: Rewrite humanizer.py**

Merge the 3-pass pipeline (LLM rewrite -> Undetectable API -> LLM restore) into:
- 1 LLM pass combining AI-pattern removal + brand voice (always)
- Undetectable.ai API (opt-in, off by default)

```python
"""
Humanizer - AI-detection removal for LinkedIn articles.

Single LLM pass: removes AI vocabulary patterns and applies brand voice.
Optional: Undetectable.ai API for statistical transformation (opt-in).
"""

import logging
import os
import time

import dspy
import httpx


class HumanizerSignature(dspy.Signature):
    """Rewrite the article to remove AI writing patterns and apply brand voice.

    REMOVE THESE AI WRITING PATTERNS:

    1. AI vocabulary words - replace with plain alternatives:
       additionally->also/and, align with->match/fit, crucial->important/critical,
       delve->explore/look at, emphasizing->noting, enduring->lasting, enhance->improve,
       fostering->building, garner->get/earn, highlight (verb)->show/point to,
       interplay->interaction, intricate/intricacies->complex/complexity,
       key (adjective)->main/core, landscape (abstract)->field/sector/industry,
       pivotal->important/decisive, showcase->show/demonstrate, tapestry->mix/combination,
       testament->proof/sign, underscore->show/confirm, valuable->useful, vibrant->active

    2. Significance inflation - remove puffed-up importance statements:
       "serves as / stands as / marks / represents [a]" -> use "is"/"are"
       "is a testament to", "underscores the importance of", "reflects broader",
       "pivotal moment", "evolving landscape", "indelible mark" -> cut or rewrite factually

    3. Promotional language - replace with neutral factual description:
       boasts, breathtaking, groundbreaking (figurative), renowned,
       stunning, must-visit, vibrant, rich (figurative), commitment to -> rewrite
       as plain statements with specific facts

    4. Superficial -ing phrases - cut trailing elaboration:
       "..., highlighting [X]", "..., underscoring [Y]", "..., reflecting [Z]" ->
       make a separate sentence or cut entirely

    5. Negative parallelisms:
       "Not only X but Y", "It's not just about X, it's about Y" -> rewrite directly

    6. Rule of three - break up forced triplets

    7. Em dash overuse - replace em dashes with commas, periods, or conjunctions

    8. Boldface overuse - remove **bold** from phrases that are not truly critical

    9. Vague attributions - remove "Experts argue", "Industry reports" -> name a specific source or cut

    10. Generic positive conclusions - replace with specific plans or facts

    11. Filler phrases - use the shorter form:
        "In order to" -> "To", "Due to the fact that" -> "Because"

    12. Excessive hedging - be direct

    13. Copula avoidance - prefer "is"/"are" over "serves as", "functions as"

    APPLY BRAND VOICE:
    - Tone: confident, professional, optimistic. Quiet boldness. No drama.
    - First-principles thinking: strip analogies, deconstruct complex systems,
      minimal text, clear logic. Write like an engineer explaining to a peer CTO.
    - Target audience: CTOs and VP Ops at tier-1 and tier-2 telcos.
    - FORBIDDEN WORDS: delve, tapestry, landscape, unlock, leverage, game-changer,
      overarching, paramount, "in conclusion", "it is important to note"
    - Never use three adjectives in a row.
    - Mix very short punchy sentences with longer technical explanations.

    ADD PERSONALITY:
    - Vary sentence rhythm. Short punchy sentences. Then longer ones.
    - Have opinions - react to facts rather than neutrally reporting them.
    - Use specific details over vague claims.
    - Acknowledge complexity and mixed feelings where real.
    - Use "I" or direct address when it fits the LinkedIn format.

    PRESERVE: all factual content, citations [text](url), and core arguments.
    """

    article: str = dspy.InputField(desc="The LinkedIn article to humanize")
    humanized_article: str = dspy.OutputField(
        desc="The rewritten article with AI patterns removed and brand voice applied. "
             "Must preserve all factual content, citations, and core arguments."
    )


class UndetectableApi:
    """Optional: Undetectable.ai humanizer API."""

    BASE_URL = "https://humanize.undetectable.ai"

    def __init__(self, api_key: str):
        self._headers = {"apikey": api_key}

    def humanize(self, text: str, on_progress=None, timeout_seconds: int = 300) -> str:
        resp = httpx.post(
            f"{self.BASE_URL}/submit",
            headers=self._headers,
            timeout=30.0,
            json={
                "content": text,
                "readability": "University",
                "purpose": "Article",
                "strength": "More Human",
                "model": "v11",
            },
        )
        resp.raise_for_status()
        doc_id = resp.json()["id"]

        for i in range(timeout_seconds // 10):
            time.sleep(10)
            elapsed = (i + 1) * 10
            if on_progress:
                on_progress("humanizing_api_progress", f"Humanizing... ({elapsed}s elapsed)")
            doc = httpx.post(
                f"{self.BASE_URL}/document",
                headers=self._headers,
                json={"id": doc_id},
                timeout=30.0,
            ).json()
            if doc.get("status") == "done":
                return doc["output"]

        raise TimeoutError(f"Undetectable.ai timed out after {timeout_seconds}s")


def humanize_article(article: str, on_progress=None, use_undetectable: bool = False) -> str:
    """
    Humanize an article: single LLM pass + optional Undetectable.ai.

    Args:
        article: Article text to humanize
        on_progress: Optional callback(stage, message)
        use_undetectable: Whether to also run through Undetectable.ai API

    Returns:
        Humanized article text
    """
    progress = on_progress or (lambda stage, msg: None)

    # Pass 1: LLM rewrite (always)
    progress("humanizing", "Rewriting for natural voice...")
    rewriter = dspy.ChainOfThought(HumanizerSignature)
    result = rewriter(article=article)
    humanized = result.humanized_article

    # Pass 2: Undetectable.ai (opt-in)
    if use_undetectable:
        api_key = os.getenv("UNDETECTABLE_API_KEY")
        if api_key:
            try:
                progress("humanizing_api", "Submitted to humanization service...")
                api = UndetectableApi(api_key)
                humanized = api.humanize(humanized, on_progress=progress)
                progress("humanizing_api_done", "Humanization service complete")
            except Exception as e:
                logging.warning(f"Undetectable.ai skipped: {e}")
        else:
            logging.info("UNDETECTABLE_API_KEY not set, skipping API humanization")

    progress("humanized", "Humanization complete")
    return humanized
```

- [ ] **Step 2: Verify module loads**

Run: `python -c "from humanizer import humanize_article; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add humanizer.py
git commit -m "simplify: humanizer is a single LLM pass, Undetectable.ai opt-in"
```

---

### Task 5: Rewrite `linkedin_article_generator.py` — single-pass pipeline

**Files:**
- Modify: `linkedin_article_generator.py`

- [ ] **Step 1: Rewrite as single-pass generator**

This is the core change. Replace the iterative improvement loop with a single-pass pipeline:
1. RAG search
2. Generate article with scoring criteria in prompt
3. Humanize
4. Optional fact-check

Progress is reported via a callback function.

```python
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
```

- [ ] **Step 2: Verify module loads**

Run: `python -c "from linkedin_article_generator import LinkedInArticleGenerator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add linkedin_article_generator.py
git commit -m "simplify: single-pass generator with callback progress"
```

---

### Task 6: Simplify `api_models.py`

**Files:**
- Modify: `api_models.py`

- [ ] **Step 1: Remove unused fields**

Remove `recreate_ctx` and `humanizer_model`. Add `fact_check` and `use_undetectable` booleans.

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add api_models.py
git commit -m "simplify: api_models with fact_check and use_undetectable flags"
```

---

### Task 7: Rewrite `api.py` for simplified generator

**Files:**
- Modify: `api.py`

- [ ] **Step 1: Rewrite api.py**

Replace `QueueOutputManager` class hierarchy with a simple callback that puts events in the queue. Use simplified `LinkedInArticleGenerator`.

```python
"""
LinkedIn Article Generator - REST API

Streaming SSE endpoint for article generation.

Event types:
  {"type": "progress", "stage": "<stage>", "message": "<text>"}
  {"type": "heartbeat"}
  {"type": "complete", "article": {...}, "score": {...}, ...}
  {"type": "error", "message": "<text>"}
"""

import asyncio
import datetime
import json
import logging
import queue
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import dspy
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from api_models import GenerateRequest
from auth import require_auth
from linkedin_article_generator import LinkedInArticleGenerator
from model_cache import API_DEFAULT_MODEL_NAME, get_cached_model, resolve_model_cached

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s  %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("li_api")

_executor = ThreadPoolExecutor(max_workers=4)


# ---------------------------------------------------------------------------
# Generation worker
# ---------------------------------------------------------------------------

def _run_generation(req: GenerateRequest, progress_queue: queue.Queue) -> None:
    """Blocking generation worker. Puts progress/complete/error events into queue."""
    try:
        default = req.model
        logger.info("Generation started - model=%s words=%d-%d", default, req.word_count_min, req.word_count_max)

        gen_cfg = resolve_model_cached(req.generator_model or default, default, temp=0.5)
        judge_cfg = resolve_model_cached(req.judge_model or default, default, temp=0.0)
        rag_cfg = resolve_model_cached(req.rag_model or default, default, temp=0.0)
        humanizer_cfg = resolve_model_cached(req.generator_model or default, default, temp=0.7)
        models = {"generator": gen_cfg, "judge": judge_cfg, "rag": rag_cfg, "humanizer": humanizer_cfg}

        logger.info("Models resolved - gen=%s judge=%s rag=%s", gen_cfg.name, judge_cfg.name, rag_cfg.name)

        def on_progress(stage: str, message: str):
            progress_queue.put({"type": "progress", "stage": stage, "message": message})

        with dspy.context(lm=gen_cfg.dspy_lm):
            generator = LinkedInArticleGenerator(
                models=models,
                word_count_min=req.word_count_min,
                word_count_max=req.word_count_max,
                on_progress=on_progress,
                fact_check=req.fact_check,
                use_undetectable=req.use_undetectable,
            )
            result = generator.generate_article(req.draft)

        logger.info("Generation complete - words=%d", result["word_count"])

        fc = result.get("fact_check_result")
        progress_queue.put({
            "type": "complete",
            "article": {
                "original": result["original_article"],
                "humanized": result["humanized_article"],
            },
            "word_count": result["word_count"],
            "fact_check": {
                "passed": fc.fact_check_passed,
                "summary": fc.summary_feedback,
            } if fc else None,
        })

    except Exception as exc:
        logger.error("Generation failed: %s\n%s", exc, traceback.format_exc())
        progress_queue.put({"type": "error", "message": str(exc)})


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    default_cfg = get_cached_model(API_DEFAULT_MODEL_NAME, temp=0.5)
    if default_cfg is None:
        raise RuntimeError(f"Cannot start API: default model '{API_DEFAULT_MODEL_NAME}' could not be resolved.")
    dspy.configure(lm=default_cfg.dspy_lm, async_max_workers=4)
    yield
    _executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LinkedIn Article Generator API",
    description="Generate LinkedIn articles via streaming SSE.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.post("/articles/generate", tags=["articles"])
async def generate_article(req: GenerateRequest, auth: dict = Depends(require_auth)):
    """Generate a LinkedIn article from a draft via SSE stream."""
    progress_queue: queue.Queue = queue.Queue()
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(_executor, _run_generation, req, progress_queue)

    async def event_stream() -> AsyncGenerator:
        while True:
            try:
                event = await loop.run_in_executor(None, lambda: progress_queue.get(timeout=0.5))
                yield {"data": json.dumps(event)}
                if event.get("type") in ("complete", "error"):
                    break
            except queue.Empty:
                if future.done():
                    break
                yield {"data": json.dumps({"type": "heartbeat"})}

    return EventSourceResponse(event_stream())
```

- [ ] **Step 2: Verify API starts**

Run: `timeout 5 python -c "from api import app; print('OK')" 2>&1 || true`
Expected: `OK` (may show model resolution messages)

- [ ] **Step 3: Commit**

```bash
git add api.py
git commit -m "simplify: api.py uses callback-based progress, no OutputManager"
```

---

### Task 8: Rewrite `main.py` — simple CLI

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Rewrite main.py**

Remove: parallel versions, MLflow, interactive menu, version export, progress dashboard.
Keep: simple CLI with draft input, model selection, file output.

```python
#!/usr/bin/env python3
"""
LinkedIn Article Generator - CLI

Usage:
    python main.py --draft "Your article outline here"
    python main.py --file path/to/draft.txt
    python main.py --file draft.txt --output article.md
"""

import argparse
import sys
import time

import dspy

from linkedin_article_generator import LinkedInArticleGenerator
from dspy_factory import get_openrouter_model, DspyModelConfig

DEFAULT_MODEL = "moonshotai/kimi-k2-thinking"


def resolve_model(name: str, fallback: str, temp: float = 0.0) -> DspyModelConfig:
    """Try name, then fallback. Raise if both fail."""
    for candidate in [name, fallback]:
        cfg = get_openrouter_model(candidate, temp=temp)
        if cfg is not None:
            return cfg
    raise RuntimeError(f"Could not resolve model: tried {name!r} and {fallback!r}")


def cli_progress(stage: str, message: str) -> None:
    """Print progress to stdout."""
    elapsed = time.time() - cli_progress.start_time
    print(f"[{elapsed:5.1f}s] [{stage.upper()}] {message}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate LinkedIn articles using DSPy with web research",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--draft", "-d", help="Article draft text")
    input_group.add_argument("--file", "-f", help="Path to draft file")

    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--word-count-min", type=int, default=2000)
    parser.add_argument("--word-count-max", type=int, default=2500)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Default model")
    parser.add_argument("--generator-model", default=DEFAULT_MODEL)
    parser.add_argument("--judge-model", default="google/gemini-3-flash-preview")
    parser.add_argument("--rag-model", default=DEFAULT_MODEL)
    parser.add_argument("--no-fact-check", action="store_true", help="Skip fact-checking")
    parser.add_argument("--use-undetectable", action="store_true", help="Use Undetectable.ai API")

    args = parser.parse_args()

    # Get draft text
    if args.draft:
        draft_text = args.draft
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                draft_text = f.read().strip()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)
    else:
        draft_text = """
# The Future of Remote Work

Remote work has fundamentally changed how we think about productivity and collaboration.

Key benefits:
- Increased flexibility for employees
- Access to global talent pool
- Reduced overhead costs

Challenges:
- Communication barriers
- Maintaining company culture
- Managing distributed teams

The future will likely be hybrid, combining the best of both worlds.
        """.strip()

    if len(draft_text.strip()) < 50:
        print("Error: Draft is too short (minimum 50 characters)")
        sys.exit(1)

    # Resolve models
    try:
        gen_cfg = resolve_model(args.generator_model, args.model, temp=0.5)
        judge_cfg = resolve_model(args.judge_model, args.model)
        rag_cfg = resolve_model(args.rag_model, args.model)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    models = {
        "generator": gen_cfg,
        "judge": judge_cfg,
        "rag": rag_cfg,
        "humanizer": gen_cfg,
    }

    print(f"Generator: {gen_cfg.name}")
    print(f"Judge:     {judge_cfg.name}")
    print(f"RAG:       {rag_cfg.name}")
    print(f"Words:     {args.word_count_min}-{args.word_count_max}")
    print()

    # Configure DSPy
    dspy.configure(lm=gen_cfg.dspy_lm)

    # Generate
    cli_progress.start_time = time.time()

    generator = LinkedInArticleGenerator(
        models=models,
        word_count_min=args.word_count_min,
        word_count_max=args.word_count_max,
        on_progress=cli_progress,
        fact_check=not args.no_fact_check,
        use_undetectable=args.use_undetectable,
    )

    try:
        result = generator.generate_article(draft_text)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Output
    article = result["humanized_article"]
    word_count = result["word_count"]

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(article)
        print(f"\nSaved to: {args.output} ({word_count} words)")
    else:
        print("\n" + "=" * 80)
        print("GENERATED ARTICLE")
        print("=" * 80)
        print(article)
        print("=" * 80)
        print(f"\n{word_count} words")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI loads**

Run: `python main.py --help`
Expected: Shows help text with simplified options

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "simplify: main.py is a simple CLI, no parallel/MLflow/interactive"
```

---

### Task 9: Delete unused files

**Files:**
- Delete: `context_window_manager.py`
- Delete: `word_count_manager.py`
- Delete: `progress_dashboard.py`
- Delete: `output_manager.py`

- [ ] **Step 1: Remove unused modules**

```bash
rm context_window_manager.py word_count_manager.py progress_dashboard.py output_manager.py
```

- [ ] **Step 2: Verify no remaining imports of deleted modules**

```bash
grep -r "from context_window_manager\|from word_count_manager\|from progress_dashboard\|from output_manager\|import context_window_manager\|import word_count_manager\|import progress_dashboard\|import output_manager" *.py
```

Expected: No output (no remaining imports)

- [ ] **Step 3: Verify the full pipeline loads end-to-end**

```bash
python -c "
from linkedin_article_generator import LinkedInArticleGenerator
from api import app
from main import main
print('All modules load successfully')
"
```

Expected: `All modules load successfully`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "simplify: remove unused modules (context_window_manager, word_count_manager, progress_dashboard, output_manager)"
```

---

### Task 10: Update `requirements.txt`

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Remove mlflow dependency**

```
pydantic
python-dotenv
dspy==3.1.3
tavily-python
beautifulsoup4
lxml
fastapi
uvicorn[standard]
sse-starlette
httpx
google-generativeai
```

Remove: `mlflow`, `attachments`, `ddgs` (not used in simplified flow).

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "simplify: remove unused dependencies (mlflow, attachments, ddgs)"
```

---

### Task 11: Smoke test the full pipeline

- [ ] **Step 1: Test CLI help**

```bash
python main.py --help
```

- [ ] **Step 2: Test API startup**

```bash
timeout 10 uvicorn api:app --port 8099 &
sleep 3
curl -s http://localhost:8099/health
kill %1 2>/dev/null
```

Expected: `{"status":"ok",...}`

- [ ] **Step 3: Final commit with updated CLAUDE.md**

Update CLAUDE.md to reflect the simplified architecture, then commit.
