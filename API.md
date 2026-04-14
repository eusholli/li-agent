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

Humanization is a separate optional step — call `POST /humanize` after generation if you want AI-pattern removal applied.

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
| `article_type` | string | no | `"thought_leadership"` | see [Article Types](#article-types) | Controls scoring criteria and content style for the generated article |
| `target_score` | number | no | `89.0` | 0–100 | Quality score % used in scoring criteria prompt |
| `max_iterations` | integer | no | `1` | 1–1 | Kept for backwards compatibility; always 1 (single-pass pipeline) |
| `word_count_min` | integer | no | `1500` | ≥100 | Minimum article word count |
| `word_count_max` | integer | no | `2000` | ≥100 | Maximum article word count |
| `model` | string | no | `"gemini/gemini-2.5-flash"` | — | Default fallback model used for all components unless overridden |
| `generator_model` | string\|null | no | `"gemini/gemini-2.5-pro"` | — | Override model for article generation |
| `judge_model` | string\|null | no | `"gemini/gemini-2.5-flash"` | — | Override model for fact-checking / quality scoring |
| `rag_model` | string\|null | no | `"gemini/gemini-2.5-flash"` | — | Override model for web search query generation |
| `fact_check` | boolean | no | `true` | — | Whether to fact-check the article against RAG sources |

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
  "article_type": "thought_leadership",
  "target_score": 85.0,
  "word_count_min": 1500,
  "word_count_max": 2000,
  "generator_model": "gemini/gemini-2.5-pro",
  "judge_model": "gemini/gemini-2.5-flash",
  "rag_model": "gemini/gemini-2.5-flash",
  "fact_check": true
}
```

---

## Article Types

The `article_type` field selects the scoring criteria and content style used during generation. Each type optimizes for a different LinkedIn content goal.

| Type key | Label | Goal |
|---|---|---|
| `thought_leadership` | Thought Leadership | Deep analytical content that challenges conventional wisdom and establishes the author as an authoritative voice. Uses first-principles thinking and strategic deconstruction. **(default)** |
| `awareness` | Awareness | Educates and builds brand recognition among people unfamiliar with the topic. Optimizes for shareability, jargon-free clarity, and attracting new followers — not selling. |
| `demand_gen` | Demand Generation | Drives qualified leads or conversions. Vividly articulates the problem, presents a credible solution with proof, handles objections, and closes with a specific CTA. |
| `event_attendance` | Event Attendance | Drives registrations for a conference, webinar, or workshop. Highlights specific event value, creates genuine FOMO, and makes registering feel effortless. |
| `recruitment` | Recruitment | Attracts qualified candidates. Authentically portrays culture, growth opportunities, and mission — speaking to what ambitious people care about, not just job requirements. |
| `product_announcement` | Product Announcement | Creates excitement for a new product or feature. Explains the problem solved, quantifies user benefits, provides early validation, and maintains credibility throughout. |
| `case_study` | Case Study | Builds credibility through a customer success story. Makes the challenge relatable, narrates the solution journey authentically, proves results with specific metrics, and extracts transferable lessons. |

**Example — demand generation article:**

```json
{
  "draft": "Companies are losing 30% of qualified leads because their follow-up takes too long...",
  "article_type": "demand_gen",
  "word_count_min": 1200,
  "word_count_max": 1600
}
```

**Example — event attendance article:**

```json
{
  "draft": "Our annual AI Summit is on June 15 in San Francisco. Last year 800 attendees joined...",
  "article_type": "event_attendance",
  "word_count_min": 800,
  "word_count_max": 1200
}
```

---

### `POST /humanize`

Humanize a pre-generated article to remove AI writing patterns and apply brand voice. This is an optional second step after `POST /articles/generate`. The response is a **Server-Sent Events stream** identical in structure to the generate endpoint.

**Authentication required.** Same Clerk JWT rules as `/articles/generate`.

**Request headers**

```
Content-Type: application/json
Accept: text/event-stream
Authorization: Bearer <clerk_jwt>
```

**Request body**

| Field | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `article` | string | yes | — | min 50 chars | Article text to humanize (use `article.text` from the generate complete event) |
| `model` | string | no | `"gemini/gemini-2.5-flash"` | — | Default fallback model |
| `humanizer_model` | string\|null | no | `null` | — | Override model for the humanization LLM pass (overrides `model`) |
| `use_undetectable` | boolean | no | `false` | — | Whether to also run through Undetectable.ai API (requires `UNDETECTABLE_API_KEY`) |
| `readability` | string | no | `"University"` | see [Undetectable.ai Parameters](#undetectableai-parameters) | Target reading level for the humanized output |
| `purpose` | string | no | `"Article"` | see [Undetectable.ai Parameters](#undetectableai-parameters) | Content type passed to Undetectable.ai |
| `strength` | string | no | `"More Human"` | `"Quality"`, `"Balanced"`, `"More Human"` | Humanization aggressiveness |
| `undetectable_model` | string | no | `"v11sr"` | `"v2"`, `"v11"`, `"v11sr"` | Undetectable.ai model — `v11sr` gives the best English results |

> All four Undetectable.ai fields (`readability`, `purpose`, `strength`, `undetectable_model`) are only used when `use_undetectable: true`. They are silently ignored otherwise.

### Undetectable.ai Parameters

**`readability`** — target reading level:

| Value | Audience |
|---|---|
| `"High School"` | General / informal |
| `"University"` | Professional (default) |
| `"Doctorate"` | Academic / research |
| `"Journalist"` | News / editorial |
| `"Marketing"` | Sales / promotional |

**`purpose`** — content type:

| Value |
|---|
| `"General Writing"` |
| `"Essay"` |
| `"Article"` (default) |
| `"Marketing Material"` |
| `"Story"` |
| `"Cover Letter"` |
| `"Report"` |
| `"Business Material"` |
| `"Legal Material"` |

**`undetectable_model`** — processing model:

| Value | Notes |
|---|---|
| `"v2"` | Multilingual, moderate humanization |
| `"v11"` | English-optimised, high-level transformation |
| `"v11sr"` | Slower, superior English results (default) |

**Minimal request example**

```json
{
  "article": "# Why AI Strategy Must Start at the Board Level\n\nMost executives think AI will automate their workforce..."
}
```

**Full request example**

```json
{
  "article": "# Why AI Strategy Must Start at the Board Level\n\nMost executives think AI will automate their workforce...",
  "humanizer_model": "gemini/gemini-2.5-pro",
  "use_undetectable": true,
  "readability": "University",
  "purpose": "Article",
  "strength": "More Human",
  "undetectable_model": "v11sr"
}
```

---

## SSE Event Stream Protocol

Both `/articles/generate` and `/humanize` use the same SSE event stream protocol. The response body is a stream of `text/event-stream` lines. Each event follows the standard SSE format:

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

### Event type: `complete` (generate)

The terminal success event from `POST /articles/generate`. The stream ends immediately after this event.

```json
{
  "type": "complete",
  "article": {
    "text": "# Article Title\n\nGenerated markdown content..."
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

**`article` object fields (generate):**

| Field | Type | Description |
|---|---|---|
| `text` | string | The generated article after fact-checking. Pass this to `POST /humanize` if humanization is desired. |

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

### Event type: `complete` (humanize)

The terminal success event from `POST /humanize`. The stream ends immediately after this event.

```json
{
  "type": "complete",
  "article": {
    "humanized": "# Article Title\n\nHumanized markdown content..."
  }
}
```

**`article` object fields (humanize):**

| Field | Type | Description |
|---|---|---|
| `humanized` | string | The article after the humanizer rewrite with AI patterns removed and brand voice applied. Use this for publishing. |

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
// ── Requests ─────────────────────────────────────────────────────────────────

export type ArticleType =
  | "thought_leadership"
  | "awareness"
  | "demand_gen"
  | "event_attendance"
  | "recruitment"
  | "product_announcement"
  | "case_study";

export interface GenerateRequest {
  draft: string;
  article_type?: ArticleType;      // default "thought_leadership"
  target_score?: number;           // default 89.0
  max_iterations?: number;         // always 1; kept for backwards compat
  word_count_min?: number;         // default 1500
  word_count_max?: number;         // default 2000
  model?: string;                  // default "gemini/gemini-2.5-flash"
  generator_model?: string | null; // default "gemini/gemini-2.5-pro"
  judge_model?: string | null;     // default "gemini/gemini-2.5-flash"
  rag_model?: string | null;       // default "gemini/gemini-2.5-flash"
  fact_check?: boolean;            // default true
}

export type UndetectableReadability =
  | "High School"
  | "University"
  | "Doctorate"
  | "Journalist"
  | "Marketing";

export type UndetectablePurpose =
  | "General Writing"
  | "Essay"
  | "Article"
  | "Marketing Material"
  | "Story"
  | "Cover Letter"
  | "Report"
  | "Business Material"
  | "Legal Material";

export type UndetectableStrength = "Quality" | "Balanced" | "More Human";

export type UndetectableModel = "v2" | "v11" | "v11sr";

export interface HumanizeRequest {
  article: string;
  model?: string;                       // default "gemini/gemini-2.5-flash"
  humanizer_model?: string | null;      // overrides model for the LLM humanization pass
  use_undetectable?: boolean;           // default false — requires UNDETECTABLE_API_KEY server-side
  readability?: UndetectableReadability; // default "University"
  purpose?: UndetectablePurpose;        // default "Article"
  strength?: UndetectableStrength;      // default "More Human"
  undetectable_model?: UndetectableModel; // default "v11sr" (best English results)
}

// ── SSE Events ───────────────────────────────────────────────────────────────

/** Progress stages emitted by /articles/generate */
export type GenerateProgressStage =
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
  | "complete_generation"
  | "info";

/** Progress stages emitted by /humanize */
export type HumanizeProgressStage =
  | "humanizing"
  | "humanized"
  | "humanizing_api"
  | "humanizing_api_progress"
  | "humanizing_api_done";

export type ProgressStage = GenerateProgressStage | HumanizeProgressStage;

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

export interface GenerateArticleResult {
  /** Generated article after fact-checking. Pass to POST /humanize for humanization. */
  text: string;
}

export interface HumanizeArticleResult {
  /** Article after humanizer rewrite — use this for publishing. */
  humanized: string;
}

export interface FactCheckResult {
  passed: boolean;
  summary: string;
}

export interface GenerateCompleteEvent {
  type: "complete";
  article: GenerateArticleResult;
  score: ArticleScore;
  /** null when fact_check: false or no RAG sources were retrieved */
  fact_check: FactCheckResult | null;
  target_achieved: boolean;
  iterations_used: number;
}

export interface HumanizeCompleteEvent {
  type: "complete";
  article: HumanizeArticleResult;
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type ArticleGeneratorEvent =
  | ProgressEvent
  | HeartbeatEvent
  | GenerateCompleteEvent
  | ErrorEvent;

export type HumanizerEvent =
  | ProgressEvent
  | HeartbeatEvent
  | HumanizeCompleteEvent
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
  HumanizeRequest,
  ArticleGeneratorEvent,
  HumanizerEvent,
  GenerateCompleteEvent,
  HumanizeCompleteEvent,
} from "./article-generator-types"; // paste the types above into this file

// ── Shared SSE streaming helper ───────────────────────────────────────────────

interface StreamCallbacks<TComplete> {
  onProgress?: (stage: string, message: string) => void;
  onComplete: (event: TComplete) => void;
  onError: (message: string) => void;
}

function streamSse<TEvent extends { type: string }, TComplete extends TEvent>(
  url: string,
  body: unknown,
  clerkToken: string,
  callbacks: StreamCallbacks<TComplete>
): AbortController {
  const controller = new AbortController();

  (async () => {
    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          Authorization: `Bearer ${clerkToken}`,
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") return;
      callbacks.onError(`Network error: ${(err as Error).message}`);
      return;
    }

    if (!response.ok) {
      const text = await response.text().catch(() => "");
      callbacks.onError(`HTTP ${response.status}: ${text}`);
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
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const dataLine = part.split("\n").find((l) => l.startsWith("data: "));
          if (!dataLine) continue;

          let event: TEvent;
          try {
            event = JSON.parse(dataLine.slice(6)) as TEvent;
          } catch {
            continue;
          }

          if (event.type === "heartbeat") {
            // keep-alive — ignore
          } else if (event.type === "progress") {
            const e = event as unknown as { stage: string; message: string };
            callbacks.onProgress?.(e.stage, e.message);
          } else if (event.type === "complete") {
            callbacks.onComplete(event as unknown as TComplete);
            return;
          } else if (event.type === "error") {
            const e = event as unknown as { message: string };
            callbacks.onError(e.message);
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

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Generate a LinkedIn article by streaming events from the API.
 *
 * Returns an AbortController — call controller.abort() to cancel.
 *
 * @example
 * const ctrl = generateArticle(
 *   "http://localhost:8000",
 *   { draft: "AI is changing everything..." },
 *   {
 *     onProgress: (stage, message) => console.log(`[${stage}] ${message}`),
 *     onComplete: (event) => setArticle(event.article.text),
 *     onError: (msg) => setError(msg),
 *   },
 *   clerkToken
 * );
 */
export function generateArticle(
  baseUrl: string,
  request: GenerateRequest,
  callbacks: StreamCallbacks<GenerateCompleteEvent>,
  clerkToken: string
): AbortController {
  return streamSse<ArticleGeneratorEvent, GenerateCompleteEvent>(
    `${baseUrl}/articles/generate`,
    request,
    clerkToken,
    callbacks
  );
}

/**
 * Humanize a pre-generated article by streaming events from the API.
 *
 * Returns an AbortController — call controller.abort() to cancel.
 *
 * @example
 * const ctrl = humanizeArticle(
 *   "http://localhost:8000",
 *   { article: generatedText },
 *   {
 *     onProgress: (stage, message) => console.log(`[${stage}] ${message}`),
 *     onComplete: (event) => setArticle(event.article.humanized),
 *     onError: (msg) => setError(msg),
 *   },
 *   clerkToken
 * );
 */
export function humanizeArticle(
  baseUrl: string,
  request: HumanizeRequest,
  callbacks: StreamCallbacks<HumanizeCompleteEvent>,
  clerkToken: string
): AbortController {
  return streamSse<HumanizerEvent, HumanizeCompleteEvent>(
    `${baseUrl}/humanize`,
    request,
    clerkToken,
    callbacks
  );
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
import { generateArticle, humanizeArticle } from "./article-generator-client";
import type {
  GenerateRequest,
  HumanizeRequest,
  GenerateCompleteEvent,
  HumanizeCompleteEvent,
} from "./article-generator-types";

export function useArticleGenerator(baseUrl: string, clerkToken: string) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [isHumanizing, setIsHumanizing] = useState(false);
  const [progressMessages, setProgressMessages] = useState<string[]>([]);
  const [generateResult, setGenerateResult] = useState<GenerateCompleteEvent | null>(null);
  const [humanizeResult, setHumanizeResult] = useState<HumanizeCompleteEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const generate = useCallback(
    (request: GenerateRequest) => {
      setIsGenerating(true);
      setProgressMessages([]);
      setGenerateResult(null);
      setHumanizeResult(null);
      setError(null);

      controllerRef.current = generateArticle(baseUrl, request, {
        onProgress: (stage, message) => {
          setProgressMessages((prev) => [...prev, `[${stage}] ${message}`]);
        },
        onComplete: (event) => {
          setGenerateResult(event);
          setIsGenerating(false);
        },
        onError: (msg) => {
          setError(msg);
          setIsGenerating(false);
        },
      }, clerkToken);
    },
    [baseUrl, clerkToken]
  );

  const humanize = useCallback(
    (request: HumanizeRequest) => {
      setIsHumanizing(true);
      setProgressMessages([]);
      setHumanizeResult(null);
      setError(null);

      controllerRef.current = humanizeArticle(baseUrl, request, {
        onProgress: (stage, message) => {
          setProgressMessages((prev) => [...prev, `[${stage}] ${message}`]);
        },
        onComplete: (event) => {
          setHumanizeResult(event);
          setIsHumanizing(false);
        },
        onError: (msg) => {
          setError(msg);
          setIsHumanizing(false);
        },
      }, clerkToken);
    },
    [baseUrl, clerkToken]
  );

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    setIsGenerating(false);
    setIsHumanizing(false);
  }, []);

  return {
    generate,
    humanize,
    cancel,
    isGenerating,
    isHumanizing,
    progressMessages,
    generateResult,
    humanizeResult,
    error,
  };
}
```

### Usage in a React component

```tsx
function ArticleGenerator() {
  const {
    generate, humanize, cancel,
    isGenerating, isHumanizing,
    progressMessages, generateResult, humanizeResult, error,
  } = useArticleGenerator("http://localhost:8000", clerkToken);

  const handleSubmit = (draft: string) => {
    generate({
      draft,
      word_count_min: 2000,
      word_count_max: 2500,
    });
  };

  const handleHumanize = () => {
    if (!generateResult) return;
    humanize({ article: generateResult.article.text });
  };

  const isBusy = isGenerating || isHumanizing;
  const publishableArticle = humanizeResult?.article.humanized ?? generateResult?.article.text;

  return (
    <div>
      {/* ... your form ... */}

      {isBusy && (
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

      {generateResult && !isGenerating && (
        <div>
          <p>Words: {generateResult.score.word_count}</p>
          {generateResult.fact_check && (
            <p>Fact-check: {generateResult.fact_check.passed ? "Passed" : "Issues found"} — {generateResult.fact_check.summary}</p>
          )}
          <button onClick={handleHumanize} disabled={isHumanizing}>
            {isHumanizing ? "Humanizing..." : "Humanize"}
          </button>
        </div>
      )}

      {publishableArticle && (
        <article>{publishableArticle}</article>
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
| `article_type` is not a valid type key | HTTP `422 Unprocessable Entity` before stream opens |
| `target_score` outside 0–100 | HTTP `422 Unprocessable Entity` |
| `max_iterations` not equal to 1 | HTTP `422 Unprocessable Entity` (locked to 1) |
| Invalid/unavailable model name | `error` event on the SSE stream |
| `OPENROUTER_API_KEY` missing or invalid | `error` event on the SSE stream |
| `TAVILY_API_KEY` missing (web search fails) | Generation continues without RAG context |
| `target_score` not reached within `max_iterations` | `complete` event with `target_achieved: false`; best article is returned |
| `article` shorter than 50 characters on `/humanize` | HTTP `422 Unprocessable Entity` before stream opens |
| `UNDETECTABLE_API_KEY` missing when `use_undetectable: true` | Undetectable.ai pass silently skipped; LLM-only result returned |
| Server not running | `fetch` throws `TypeError: Failed to fetch` |

---

## Performance Notes

- Generation typically takes **5–20 minutes** depending on `max_iterations` and model speed.
- Keep the HTTP connection open for the full duration. Do not set short fetch timeouts.
- The `heartbeat` event is emitted every ~0.5 s to prevent proxy/browser connection timeouts.
- For production deployments behind nginx, set `proxy_read_timeout 1800;` (30 min).
- The server uses `--workers 1`. Multiple concurrent requests are supported (up to 4 in-flight at once via the internal thread pool) but they share the same process.
