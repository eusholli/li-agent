# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A DSPy-based system that transforms article drafts into polished LinkedIn articles through iterative LLM-driven generation, scoring, and improvement. It uses web research (Tavily), a 180-point scoring system, and an iterative REACT loop to reach a target quality score. Also ships as a REST API with SSE streaming and optional AI detection/humanization.

## Running the Application

```bash
# Activate virtual environment first
source venv/bin/activate

# Basic run with a draft
python main.py --draft "Your article outline here"

# From a file
python main.py --file path/to/draft.txt

# Generate multiple parallel versions for comparison
python main.py --versions 3 --file draft.txt

# Key options
python main.py --target-score 85 --max-iterations 5 --verbose --output article.md
```

Key CLI flags: `--draft/-d`, `--file/-f`, `--target-score/-t` (default 89.0), `--max-iterations/-i` (default 10), `--versions` (1-5), `--verbose/-v`, `--auto/-a` (no user interaction), `--output/-o`.

## Environment Setup

Requires a `.env` file with:
```
OPENROUTER_API_KEY="sk-or-v1-..."
TAVILY_API_KEY="tvly-dev-..."
```

Optional for API AI detection:
```
UNDETECTABLE_API_KEY="api_..."  # For AI detection via Undetectable API
```

Default LLM: `moonshotai/kimi-k2` via OpenRouter. Models can be overridden with `--generator-model`, `--judge-model`, `--rag-model`.

## Architecture

**Generation Loop** (in `linkedin_article_generator.py`):
1. RAG retrieval → `rag_fast.py` does async Tavily web search, packs results into token budget
2. Article generation → DSPy `ArticleGenerationSignature`
3. Scoring → `li_article_judge.py` returns 0-180 point score with category breakdown
4. If score < target: DSPy `ArticleImprovementSignature` with gap analysis, repeat
5. If score ≥ target or max iterations reached: output final article

**Scoring System** (`li_article_judge.py`, 180 points total):
- Core Thinking: 120 pts (First-Order Thinking 45pts + Strategic Deconstruction 75pts)
- Content Quality: 60 pts (Hook, Storytelling, Authority, Clarity, Value, CTA — 10pts each)
- Tiers: 89%+ World-class, 72%+ Strong, 56%+ Needs restructuring, <56% Rework

**Parallel Versions** (`main.py`): Uses DSPy's Parallel module with temperatures [0.1, 0.5, 0.9, 0.3, 0.7] per version slot. All versions run independently, then user selects best.

**Key modules:**
- `main.py` — CLI, orchestration, parallel execution
- `linkedin_article_generator.py` — Core iterative generation loop with REACT phases
- `li_article_judge.py` — Comprehensive scoring with fact-checking and detailed category breakdown
- `rag_fast.py` — Async web search and token-aware content packing
- `dspy_factory.py` — OpenRouter/OpenAI/Anthropic/Ollama model resolution and DSPy LM setup
- `models.py` — Pydantic models: `ArticleVersion`, `JudgementModel`, `ArticleScoreModel`
- `context_window_manager.py` — Token budget management: 40% instructions / 30% RAG / 30% safety
- `word_count_manager.py` — Enforces 2000-2500 word range with gap analysis
- `output_manager.py` — Console output formatting for single and parallel modes
- `progress_dashboard.py` — Score tier translation and user-facing progress visualization
- `humanizer.py` — Optional humanization of AI-generated text using Undetectable API
- `api.py` — FastAPI server with SSE streaming, authentication, and fact-checking

**API-specific modules:**
- `api_models.py` — Pydantic schemas for API requests/responses
- `auth.py` — Clerk JWT authentication for the API

See `FACT_CHECK_IMPLEMENTATION.md`, `humanizer.md`, and `API.md` for detailed implementation notes on scoring, humanization, and API behavior.

## DSPy Patterns

Signatures are defined with `dspy.Signature` classes. Key signatures in `linkedin_article_generator.py`:
- `ArticleGenerationSignature` — Takes instructions + RAG context, outputs article
- `ArticleImprovementSignature` — Takes current article + gap analysis, outputs improved version

Modules use `dspy.ChainOfThought` or `dspy.Predict`. Model setup via `dspy.configure(lm=...)` happens in `main.py` before module instantiation. For API, setup is in `api.py`'s startup event.

## Testing

**Integration test for the API:**
```bash
# Start API first
uvicorn api:app --port 8000

# In another terminal, test with a Clerk token
python test_api.py --token YOUR_JWT --score 72 --min-words 600 --max-words 900
```

The test client streams SSE events in real-time and displays the final article. Use `--url http://localhost:PORT` to test non-local deployments.

No traditional unit test suite exists; the system is tested end-to-end via the CLI and API clients.

## API Server

```bash
# Run locally
uvicorn api:app --host 0.0.0.0 --port 8000

# Docker deployment (see docker-compose.yml, docker-compose.prod.yml, deploy-prod.sh)
docker compose up -d --build
```

The API (`api.py`) accepts `/articles/generate` POST requests with a draft, returns SSE stream of progress events, and includes optional AI detection and humanization. Requires Clerk authentication. See `API.md` for full endpoint docs.

## Development Tips

**Adding new models:** Edit `dspy_factory.py`'s `MODEL_CONFIGS` dict to register new OpenRouter/OpenAI/Anthropic models. The CLI flags `--generator-model`, `--judge-model`, `--rag-model` accept format `provider/model-name` (e.g., `openrouter/anthropic/claude-3-sonnet`).

**Debugging scoring:** The judge returns detailed category scores in `ArticleScoreModel`. Check `li_article_judge.py:ArticleJudge` to understand how each of the 18 criteria contributes to the 180-point total. Run with `--verbose` to see category breakdowns per iteration.

**RAG troubleshooting:** If web search returns no results or wrong context, check `rag_fast.py`. The system extracts search queries via DSPy's `TopicExtractionSignature`, then packs results into the token budget. If context isn't helping, the draft may need stronger signals for what to search.

**Token budget:** `context_window_manager.py` splits the context window 40% instructions / 30% RAG / 30% safety. If RAG content is being cut off, lower the word count target or use smaller models.

**Parallel versions:** Uses threading, not multiprocessing. DSPy's `Parallel` module runs each version independently with its own LM configuration and temperature.

## Dependencies

Install with: `pip install -r requirements.txt`

Key packages: `dspy==3.1.3`, `pydantic`, `python-dotenv`, `tavily-python`, `beautifulsoup4`, `fastapi`, `uvicorn`, `sse-starlette`, `httpx`, `google-generativeai`, `mlflow`, `attachments`.
