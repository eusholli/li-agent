#!/usr/bin/env python3
"""
Simple test client for the LinkedIn Article Generator API.

Connects to the SSE stream, prints progress events in real time,
and displays the final generated article.

Usage:
    python test_api.py --token <clerk_jwt> [--url http://localhost:8000] [--score 75] [--iterations 3]

Requirements:
    pip install httpx
"""

import argparse
import json
import sys
import time

import httpx

# Short draft for fast testing — reduce target_score and word counts below
SAMPLE_DRAFT = """
The most dangerous assumption in business today is that AI will simply automate
existing work. That framing misses everything important.

Real AI transformation isn't about doing the same things faster. It's about
rethinking which problems are worth solving, which decisions require human
judgment, and where speed of learning — not speed of execution — becomes the
true competitive advantage.

Three patterns I've observed in companies getting this right, and why most
others are still missing the point entirely.
"""


def run_test(
    api_url: str,
    token: str,
    target_score: float,
    max_iterations: int,
    word_count_min: int,
    word_count_max: int,
) -> int:
    """
    Run a single generation test.  Returns 0 on success, 1 on error.
    """
    payload = {
        "draft": SAMPLE_DRAFT.strip(),
        "target_score": target_score,
        "max_iterations": max_iterations,
        "word_count_min": word_count_min,
        "word_count_max": word_count_max,
    }

    generate_url = f"{api_url.rstrip('/')}/articles/generate"
    print(f"POST {generate_url}")
    print(
        f"  target_score={target_score}  max_iterations={max_iterations}  "
        f"words={word_count_min}-{word_count_max}\n"
    )

    start = time.time()

    try:
        with httpx.Client(timeout=None) as client:
            with client.stream(
                "POST",
                generate_url,
                json=payload,
                headers={
                    "Accept": "text/event-stream",
                    "Authorization": f"Bearer {token}",
                },
            ) as response:
                if response.status_code != 200:
                    print(f"ERROR: HTTP {response.status_code}", file=sys.stderr)
                    print(response.text, file=sys.stderr)
                    return 1

                heartbeat_count = 0

                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue

                    raw = line[len("data: ") :]
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    etype = event.get("type")

                    if etype == "progress":
                        stage = event.get("stage", "").upper()
                        message = event.get("message", "")
                        elapsed = time.time() - start
                        print(f"  [{elapsed:6.1f}s] [{stage}] {message}")
                        heartbeat_count = 0  # reset heartbeat counter on real event

                    elif etype == "heartbeat":
                        heartbeat_count += 1
                        if heartbeat_count % 6 == 0:  # print every ~3 seconds
                            print(
                                f"  [{time.time() - start:6.1f}s] waiting...",
                                flush=True,
                            )

                    elif etype == "complete":
                        elapsed = time.time() - start
                        score = event.get("score", {})
                        detection = event.get("detection")
                        print(f"\n{'=' * 70}")
                        print(f"  COMPLETE in {elapsed:.1f}s")
                        print(
                            f"  Score:          {score.get('percentage', 0):.1f}% "
                            f"({score.get('performance_tier', 'N/A')})"
                        )
                        print(f"  Word count:     {score.get('word_count', 0)}")
                        print(
                            f"  Target achieved:{' YES' if event.get('target_achieved') else ' NO'}"
                        )
                        print(f"  Iterations used:{event.get('iterations_used', '?')}")
                        if score.get("overall_feedback"):
                            print(f"\n  Feedback: {score['overall_feedback'][:200]}...")

                        if detection:
                            print(f"\n  --- AI Detection Scores ---")
                            for which in ("original", "humanized"):
                                d = detection.get(which)
                                if d:
                                    print(
                                        f"  {which.capitalize():10s}  "
                                        f"AI: {d.get('ai_score', 0):.0f}%  "
                                        f"Human: {d.get('human_score', 0):.0f}%"
                                    )
                                    per = d.get("per_detector", {})
                                    if per:
                                        scores_str = "  ".join(
                                            f"{k}: {v:.0f}%" for k, v in per.items() if v is not None
                                        )
                                        print(f"             {scores_str}")
                        else:
                            print(f"\n  Detection: not available (UNDETECTABLE_API_KEY not set)")

                        print(f"{'=' * 70}")

                        article_obj = event.get("article", {})
                        humanized = article_obj.get("humanized", "")
                        original = article_obj.get("original", "")
                        if humanized:
                            print(f"\n--- HUMANIZED ARTICLE ---\n")
                            print(humanized)
                        if original and original != humanized:
                            print(f"\n--- ORIGINAL ARTICLE (pre-humanization) ---\n")
                            print(original)
                        return 0

                    elif etype == "error":
                        elapsed = time.time() - start
                        print(
                            f"\nERROR after {elapsed:.1f}s: {event.get('message', 'unknown error')}",
                            file=sys.stderr,
                        )
                        return 1

    except httpx.ConnectError:
        print(
            f"ERROR: Could not connect to {api_url}. Is the server running?",
            file=sys.stderr,
        )
        print("  Start it with:  uvicorn api:app --port 8000", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 1

    return 0


def check_health(api_url: str) -> bool:
    """Check /health before attempting generation."""
    try:
        r = httpx.get(f"{api_url.rstrip('/')}/health", timeout=10)
        data = r.json()
        print(
            f"Health check: {data.get('status')} (server time: {data.get('timestamp')})\n"
        )
        return data.get("status") == "ok"
    except Exception as exc:
        print(f"Health check failed: {exc}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test the LinkedIn Article Generator API"
    )
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument(
        "--token",
        required=True,
        help="Clerk JWT for authentication (role must be root or marketing)",
    )
    parser.add_argument(
        "--score",
        type=float,
        default=72.0,
        help="Target score %% (lower = faster test, default: 72)",
    )
    parser.add_argument(
        "--iterations", type=int, default=3, help="Max iterations (default: 3)"
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=600,
        help="Min word count (default: 600 for fast test)",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=900,
        help="Max word count (default: 900 for fast test)",
    )
    args = parser.parse_args()

    if not check_health(args.url):
        sys.exit(1)

    sys.exit(
        run_test(args.url, args.token, args.score, args.iterations, args.min_words, args.max_words)
    )


if __name__ == "__main__":
    main()
