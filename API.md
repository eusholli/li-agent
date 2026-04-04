# LinkedIn Article Generator — API Reference

Base URL: `http://<host>:8000`
Protocol: HTTP/1.1 with Server-Sent Events (SSE) for streaming
Auth: Clerk JWT Bearer token (roles `root` or `marketing` required)
CORS: All origins permitted

---

## Endpoints

### `GET /health`

Health check. Use this to confirm the server is up before initiating generation.

**Response `200 OK`**

```json
{
  "status": "ok",
  "timestamp": "2026-03-29T14:00:00.000000"
}
```

---

### `POST /articles/generate`

Generate a LinkedIn article. The response is a **Server-Sent Events stream** that delivers real-time progress events followed by the completed article.

**Authentication required.** Include a valid Clerk JWT in the `Authorization` header. The user's role (from `publicMetadata.role` in Clerk) must be `root` or `marketing`. Other roles receive `403 Forbidden`.

**Request headers**

```
Content-Type: application/json
Accept: text/event-stream
Authorization: Bearer <clerk_jwt>
```

**Request body**

| Field | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `draft` | string | yes | — | min 50 chars | Article draft, outline, or topic description |
| `target_score` | number | no | `89.0` | 0–100 | Quality score % used in scoring criteria prompt |
| `max_iterations` | integer | no | `1` | 1–1 | Kept for backwards compatibility; always 1 (single-pass pipeline) |
| `word_count_min` | integer | no | `1500` | ≥100 | Minimum article word count |
| `word_count_max` | integer | no | `2000` | ≥100 | Maximum article word count |
| `model` | string | no | `"gemini/gemini-2.5-flash"` | — | Default fallback model used for all components unless overridden |
| `generator_model` | string\|null | no | `"gemini/gemini-2.5-pro"` | — | Override model for article generation |
| `judge_model` | string\|null | no | `"gemini/gemini-2.5-flash"` | — | Override model for fact-checking / quality scoring |
| `rag_model` | string\|null | no | `"gemini/gemini-2.5-flash"` | — | Override model for web search query generation |
| `fact_check` | boolean | no | `true` | — | Whether to fact-check the article against RAG sources |
| `use_undetectable` | boolean | no | `false` | — | Whether to run through Undetectable.ai API (requires `UNDETECTABLE_API_KEY`) |

Model strings are DSPy-compatible model IDs. The default models use Google Gemini (requires `GEMINI_API_KEY`). OpenRouter models (e.g. `"openrouter/anthropic/claude-3-5-sonnet"`) require `OPENROUTER_API_KEY`.

**Minimal request example**

```json
{
  "draft": "Most executives think AI will automate their workforce. They're asking the wrong question entirely. The real transformation is happening at the strategy layer, not the operations layer."
}
```

**Full request example**

```json
{
  "draft": "Most executives think AI will automate their workforce...",
  "target_score": 85.0,
  "word_count_min": 1500,
  "word_count_max": 2000,
  "generator_model": "gemini/gemini-2.5-pro",
  "judge_model": "gemini/gemini-2.5-flash",
  "rag_model": "gemini/gemini-2.5-flash",
  "fact_check": true,
  "use_undetectable": false
}
```

---

## SSE Event Stream Protocol

The response body is a stream of `text/event-stream` lines. Each event follows the standard SSE format:

```
data: <JSON>\n\n
```

All events are JSON objects. The `type` field determines the shape of the rest of the object.

### Event type: `progress`

Emitted continuously throughout generation to report the current stage.

```json
{
  "type": "progress",
  "stage": "string",
  "message": "string"
}
```

**All possible `stage` values, in order of occurrence:**

| Stage | When emitted |
|---|---|
| `init` | Pipeline initialisation |
| `start` | Generation loop begins |
| `rag_search` | Web search starting |
| `rag_queries` | Search queries chosen |
| `rag_complete` | Web search done, context ready |
| `context` | Context reuse/refresh decision |
| `generating` | LLM generating article (may repeat each iteration) |
| `scoring` | Judge evaluating current version |
| `scored` | Score received; message includes percentage and tier |
| `fact_checking` | Fact-check starting (only when score target is met) |
| `fact_check_results` | Fact-check summary |
| `fact_check_passed` | Article cleared by fact-checker |
| `fact_check_failed` | Fact-check found issues (article still returned) |
| `citation_issues` | Specific citation problems found |
| `humanizing` | Humanization rewrite starting (Pass 1 LLM) |
| `humanized` | Humanization complete |
| `humanizing_api` | Submitted to Undetectable.ai humanization service, waiting for result |
| `humanizing_api_progress` | Polling Undetectable.ai; message includes elapsed seconds |
| `humanizing_api_done` | Undetectable.ai humanization complete |
| `detecting_original` | AI detection check starting on the original (pre-humanization) article |
| `detecting_humanized` | AI detection check starting on the humanized article |
| `detecting_progress` | Polling AI detector; message includes elapsed seconds |
| `detected_original` | Detection complete for original article; message includes human/AI % |
| `detected_humanized` | Detection complete for humanized article; message includes human/AI % |
| `complete_version` | Internal version complete |
| `info` | General informational message |

> **Note on `humanizing_api` stages:** These events are only emitted when `UNDETECTABLE_API_KEY` is configured server-side. When the key is absent, the pipeline runs LLM-only (Pass 1 + Pass 3) and `detection` in the `complete` event will be `null`.

### Event type: `heartbeat`

Keep-alive ping emitted every ~0.5 s when the worker is busy but has no new progress to report. **Ignore the payload entirely.**

```json
{"type": "heartbeat"}
```

### Event type: `complete`

The terminal success event. The stream ends immediately after this event.

```json
{
  "type": "complete",
  "article": {
    "original": "# Article Title\n\nPre-humanization markdown...",
    "humanized": "# Article Title\n\nPost-humanization markdown..."
  },
  "score": {
    "percentage": null,
    "performance_tier": null,
    "word_count": 2187,
    "meets_requirements": true,
    "overall_feedback": "Strong strategic framing with well-supported claims."
  },
  "fact_check": {
    "passed": true,
    "summary": "All claims verified against retrieved sources."
  },
  "target_achieved": true,
  "iterations_used": 1
}
```

> **`fact_check` is `null`** when `fact_check: false` is set in the request or when no RAG sources were retrieved.

**`article` object fields:**

| Field | Type | Description |
|---|---|---|
| `original` | string | The article after generation and fact-checking, before humanization |
| `humanized` | string | The article after the humanizer rewrite. Use this for publishing. If humanization fails, equals `original`. |

**`score` object fields:**

| Field | Type | Description |
|---|---|---|
| `percentage` | null | Always `null` in the current single-pass pipeline (scoring loop removed) |
| `performance_tier` | null | Always `null` in the current single-pass pipeline |
| `word_count` | integer | Word count of the generated article |
| `meets_requirements` | boolean | Always `true` in the current pipeline |
| `overall_feedback` | string\|null | Fact-check summary feedback, or `null` when fact-checking is disabled |

**`fact_check` object fields:**

| Field | Type | Description |
|---|---|---|
| `fact_check` | object\|null | Fact-check results, or `null` when `fact_check: false` or no RAG context |
| `fact_check.passed` | boolean | Whether the fact-checker cleared the article |
| `fact_check.summary` | string | Human-readable fact-check summary |

**`target_achieved`**: Always `true` in the current single-pass pipeline. **`iterations_used`**: Always `1`.

### Event type: `error`

The terminal failure event. The stream ends immediately after this event.

```json
{
  "type": "error",
  "message": "Could not resolve model 'bad-model-name': ..."
}
```

---

## TypeScript Types

Copy these into your project for fully typed SSE handling.

```typescript
// ── Request ──────────────────────────────────────────────────────────────────

export interface GenerateRequest {
  draft: string;
  target_score?: number;        // default 89.0
  max_iterations?: number;      // always 1; kept for backwards compat
  word_count_min?: number;      // default 1500
  word_count_max?: number;      // default 2000
  model?: string;               // default "gemini/gemini-2.5-flash"
  generator_model?: string | null; // default "gemini/gemini-2.5-pro"
  judge_model?: string | null;     // default "gemini/gemini-2.5-flash"
  rag_model?: string | null;       // default "gemini/gemini-2.5-flash"
  fact_check?: boolean;         // default true
  use_undetectable?: boolean;   // default false
}

// ── SSE Events ───────────────────────────────────────────────────────────────

export type ProgressStage =
  | "init"
  | "start"
  | "rag_search"
  | "rag_queries"
  | "rag_complete"
  | "context"
  | "generating"
  | "scoring"
  | "scored"
  | "fact_checking"
  | "fact_check_results"
  | "fact_check_passed"
  | "fact_check_failed"
  | "citation_issues"
  | "humanizing"
  | "humanized"
  | "humanizing_api"
  | "humanizing_api_progress"
  | "humanizing_api_done"
  | "detecting_original"
  | "detecting_humanized"
  | "detecting_progress"
  | "detected_original"
  | "detected_humanized"
  | "complete_version"
  | "info";

export interface ProgressEvent {
  type: "progress";
  stage: ProgressStage;
  message: string;
}

export interface HeartbeatEvent {
  type: "heartbeat";
}

export interface ArticleScore {
  /** Always null in the current single-pass pipeline */
  percentage: null;
  /** Always null in the current single-pass pipeline */
  performance_tier: null;
  word_count: number;
  meets_requirements: boolean;
  /** Fact-check summary feedback, or null when fact-checking is disabled */
  overall_feedback: string | null;
}

export interface ArticleResult {
  /** Pre-humanization article — use for quality review or diff comparison */
  original: string;
  /** Post-humanization article — use this for publishing */
  humanized: string;
}

export interface FactCheckResult {
  passed: boolean;
  summary: string;
}

export interface CompleteEvent {
  type: "complete";
  article: ArticleResult;
  score: ArticleScore;
  /** null when fact_check: false or no RAG sources were retrieved */
  fact_check: FactCheckResult | null;
  target_achieved: boolean;
  iterations_used: number;
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type ArticleGeneratorEvent =
  | ProgressEvent
  | HeartbeatEvent
  | CompleteEvent
  | ErrorEvent;

// ── Health ───────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: "ok";
  timestamp: string; // ISO 8601
}
```

---

## JavaScript / TypeScript Client

A complete, copy-paste ready client using the browser's native `fetch` API. No external dependencies required.

```typescript
import type {
  GenerateRequest,
  ArticleGeneratorEvent,
  ArticleResult,
  ProgressEvent,
  CompleteEvent,
  ErrorEvent,
} from "./article-generator-types"; // paste the types above into this file

export interface GenerationCallbacks {
  /** Called for every progress stage update */
  onProgress?: (stage: string, message: string) => void;
  /** Called when generation completes successfully */
  onComplete: (event: CompleteEvent) => void;
  /** Called when generation fails */
  onError: (message: string) => void;
}

/**
 * Generate a LinkedIn article by streaming events from the API.
 *
 * Returns an AbortController — call controller.abort() to cancel the request.
 *
 * @example
 * const ctrl = generateArticle(
 *   "http://localhost:8000",
 *   { draft: "AI is changing everything..." },
 *   {
 *     onProgress: (stage, message) => console.log(`[${stage}] ${message}`),
 *     onComplete: (event) => setArticle(event.article.humanized),
 *     onError: (msg) => setError(msg),
 *   }
 * );
 * // To cancel: ctrl.abort();
 */
export function generateArticle(
  baseUrl: string,
  request: GenerateRequest,
  callbacks: GenerationCallbacks,
  clerkToken: string
): AbortController {
  const controller = new AbortController();

  (async () => {
    let response: Response;

    try {
      response = await fetch(`${baseUrl}/articles/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          Authorization: `Bearer ${clerkToken}`,
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") return;
      callbacks.onError(`Network error: ${(err as Error).message}`);
      return;
    }

    if (!response.ok) {
      const body = await response.text().catch(() => "");
      callbacks.onError(`HTTP ${response.status}: ${body}`);
      return;
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE lines are separated by double newlines
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? ""; // keep the incomplete trailing chunk

        for (const part of parts) {
          const dataLine = part
            .split("\n")
            .find((line) => line.startsWith("data: "));
          if (!dataLine) continue;

          let event: ArticleGeneratorEvent;
          try {
            event = JSON.parse(dataLine.slice(6)) as ArticleGeneratorEvent;
          } catch {
            continue; // malformed line — skip
          }

          if (event.type === "heartbeat") {
            // Keep-alive — nothing to do
          } else if (event.type === "progress") {
            callbacks.onProgress?.(event.stage, event.message);
          } else if (event.type === "complete") {
            callbacks.onComplete(event);
            return;
          } else if (event.type === "error") {
            callbacks.onError(event.message);
            return;
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") return;
      callbacks.onError(`Stream error: ${(err as Error).message}`);
    } finally {
      reader.releaseLock();
    }
  })();

  return controller;
}

/** Check that the API server is reachable. */
export async function checkHealth(baseUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl}/health`);
    const data = await res.json();
    return data.status === "ok";
  } catch {
    return false;
  }
}
```

### React hook example

```tsx
import { useState, useRef, useCallback } from "react";
import { generateArticle } from "./article-generator-client";
import type { GenerateRequest, CompleteEvent } from "./article-generator-types";

interface UseArticleGeneratorReturn {
  generate: (request: GenerateRequest) => void;
  cancel: () => void;
  isGenerating: boolean;
  progressMessages: string[];
  result: CompleteEvent | null;
  error: string | null;
}

export function useArticleGenerator(baseUrl: string): UseArticleGeneratorReturn {
  const [isGenerating, setIsGenerating] = useState(false);
  const [progressMessages, setProgressMessages] = useState<string[]>([]);
  const [result, setResult] = useState<CompleteEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const generate = useCallback(
    (request: GenerateRequest) => {
      setIsGenerating(true);
      setProgressMessages([]);
      setResult(null);
      setError(null);

      controllerRef.current = generateArticle(baseUrl, request, {
        onProgress: (stage, message) => {
          setProgressMessages((prev) => [...prev, `[${stage}] ${message}`]);
        },
        onComplete: (event) => {
          setResult(event);
          setIsGenerating(false);
        },
        onError: (msg) => {
          setError(msg);
          setIsGenerating(false);
        },
      });
    },
    [baseUrl]
  );

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    setIsGenerating(false);
  }, []);

  return { generate, cancel, isGenerating, progressMessages, result, error };
}
```

### Usage in a React component

```tsx
function ArticleGenerator() {
  const { generate, cancel, isGenerating, progressMessages, result, error } =
    useArticleGenerator("http://localhost:8000");

  const handleSubmit = (draft: string) => {
    generate({
      draft,
      target_score: 89.0,
      max_iterations: 10,
      word_count_min: 2000,
      word_count_max: 2500,
    });
  };

  return (
    <div>
      {/* ... your form ... */}

      {isGenerating && (
        <div>
          <button onClick={cancel}>Cancel</button>
          <ul>
            {progressMessages.map((msg, i) => (
              <li key={i}>{msg}</li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {result && (
        <div>
          <p>Words: {result.score.word_count} | Iterations: {result.iterations_used}</p>
          {result.fact_check && (
            <p>Fact-check: {result.fact_check.passed ? "✅ Passed" : "⚠️ Issues found"} — {result.fact_check.summary}</p>
          )}
          <article>{result.article.humanized}</article>
        </div>
      )}
    </div>
  );
}
```

---

## Environment Variables

The API server requires these variables in `.env` or the process environment:

| Variable | Required | Description |
|---|---|---|
| `WEBAPP_URL` | yes (auth) | Base URL of the event-planner webapp, e.g. `https://events.example.com` |
| `CRON_SECRET_KEY` | yes (auth) | Shared secret for calling `/api/intelligence/session` on event-planner |
| `GEMINI_API_KEY` | yes | Google Gemini API key — required for the default `gemini/gemini-2.5-*` models |
| `OPENROUTER_API_KEY` | no | OpenRouter key (for non-Gemini model overrides) |
| `TAVILY_API_KEY` | no | Tavily web search API key (RAG context) |
| `UNDETECTABLE_API_KEY` | no | Undetectable.ai key — required when `use_undetectable: true` |

---

## Error Reference

| Scenario | Behaviour |
|---|---|
| Missing `Authorization` header | HTTP `403 Forbidden` |
| Invalid or expired Clerk JWT | HTTP `401 Unauthorized` |
| Valid JWT but role not `root`/`marketing` | HTTP `403 Forbidden` |
| Auth service (`WEBAPP_URL`) unreachable | HTTP `503 Service Unavailable` |
| `WEBAPP_URL` or `CRON_SECRET_KEY` not set | HTTP `500 Internal Server Error` |
| `draft` shorter than 50 characters | HTTP `422 Unprocessable Entity` before stream opens |
| `target_score` outside 0–100 | HTTP `422 Unprocessable Entity` |
| `max_iterations` not equal to 1 | HTTP `422 Unprocessable Entity` (locked to 1) |
| Invalid/unavailable model name | `error` event on the SSE stream |
| `OPENROUTER_API_KEY` missing or invalid | `error` event on the SSE stream |
| `TAVILY_API_KEY` missing (web search fails) | Generation continues without RAG context |
| `target_score` not reached within `max_iterations` | `complete` event with `target_achieved: false`; best article is returned |
| Server not running | `fetch` throws `TypeError: Failed to fetch` |

---

## Performance Notes

- Generation typically takes **5–20 minutes** depending on `max_iterations` and model speed.
- Keep the HTTP connection open for the full duration. Do not set short fetch timeouts.
- The `heartbeat` event is emitted every ~0.5 s to prevent proxy/browser connection timeouts.
- For production deployments behind nginx, set `proxy_read_timeout 1800;` (30 min).
- The server uses `--workers 1`. Multiple concurrent requests are supported (up to 4 in-flight at once via the internal thread pool) but they share the same process.
