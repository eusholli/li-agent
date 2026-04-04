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
