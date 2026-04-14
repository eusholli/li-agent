"""
LinkedIn Article Generator - REST API

Streaming SSE endpoints for article generation and humanization.

Event types:
  {"type": "progress", "stage": "<stage>", "message": "<text>"}
  {"type": "heartbeat"}
  {"type": "complete", "article": {...}, "score": {...}, ...}  (generate)
  {"type": "complete", "article": {"humanized": "<text>"}}     (humanize)
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

from api_models import GenerateRequest, HumanizeRequest
from auth import require_auth
from humanizer import humanize_article
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
        models = {"generator": gen_cfg, "judge": judge_cfg, "rag": rag_cfg}

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
                article_type=req.article_type,
            )
            result = generator.generate_article(req.draft)

        logger.info("Generation complete - words=%d", result["word_count"])

        fc = result.get("fact_check_result")
        progress_queue.put({
            "type": "complete",
            "article": {
                "text": result["article"],
            },
            "score": {
                "word_count": result["word_count"],
                "percentage": None,
                "performance_tier": None,
                "meets_requirements": True,
                "overall_feedback": fc.summary_feedback if fc else None,
            },
            "target_achieved": True,
            "iterations_used": 1,
            "fact_check": {
                "passed": fc.fact_check_passed,
                "summary": fc.summary_feedback,
            } if fc else None,
        })

    except Exception as exc:
        logger.error("Generation failed: %s\n%s", exc, traceback.format_exc())
        progress_queue.put({"type": "error", "message": str(exc)})


def _run_humanization(req: HumanizeRequest, progress_queue: queue.Queue) -> None:
    """Blocking humanization worker. Puts progress/complete/error events into queue."""
    try:
        default = req.model
        logger.info("Humanization started - model=%s undetectable=%s", default, req.use_undetectable)

        humanizer_cfg = resolve_model_cached(req.humanizer_model or default, default, temp=0.7)
        logger.info("Model resolved - humanizer=%s", humanizer_cfg.name)

        def on_progress(stage: str, message: str):
            progress_queue.put({"type": "progress", "stage": stage, "message": message})

        with dspy.context(lm=humanizer_cfg.dspy_lm):
            humanized = humanize_article(
                req.article,
                on_progress=on_progress,
                use_undetectable=req.use_undetectable,
                readability=req.readability,
                purpose=req.purpose,
                strength=req.strength,
                undetectable_model=req.undetectable_model,
            )

        logger.info("Humanization complete")
        progress_queue.put({
            "type": "complete",
            "article": {
                "humanized": humanized,
            },
        })

    except Exception as exc:
        logger.error("Humanization failed: %s\n%s", exc, traceback.format_exc())
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


def _make_event_stream(progress_queue: queue.Queue, future, loop) -> AsyncGenerator:
    """Shared SSE event stream generator for all streaming endpoints."""
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
    return event_stream()


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.post("/articles/generate", tags=["articles"])
async def generate_article(req: GenerateRequest, auth: dict = Depends(require_auth)):
    """Generate a LinkedIn article from a draft via SSE stream."""
    progress_queue: queue.Queue = queue.Queue()
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(_executor, _run_generation, req, progress_queue)
    return EventSourceResponse(_make_event_stream(progress_queue, future, loop))


@app.post("/humanize", tags=["articles"])
async def humanize_article_endpoint(req: HumanizeRequest, auth: dict = Depends(require_auth)):
    """Humanize a pre-generated article via SSE stream."""
    progress_queue: queue.Queue = queue.Queue()
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(_executor, _run_humanization, req, progress_queue)
    return EventSourceResponse(_make_event_stream(progress_queue, future, loop))
