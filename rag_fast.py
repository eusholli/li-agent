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
