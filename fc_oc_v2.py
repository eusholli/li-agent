#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-Call Markdown Fact Checker and Rewriter with DSPy v3.0.3 + GEPA optimization

Overview
--------
This script demonstrates how to collapse a multi-call fact-checking pipeline into a
single LLM call using DSPy. It defines a single Signature and a Module that performs
the entire job in one Predict() call:
  • Validate facts against provided sources/context.
  • Rewrite or generalize uncitable claims.
  • Produce a structured change report.

It also includes an optional GEPA optimization loop to improve prompt quality over a
small train/dev set.

Requirements
------------
- Python 3.9+
- dspy==3.0.3 (pip install dspy-ai==3.0.3)  # package name may be `dspy-ai`
- A supported LLM provider set via dspy.settings.configure(lm=...)
  (e.g., OpenAI, Anthropic, Azure OpenAI, etc.)

Inputs
------
- An article markdown file (default: /mnt/data/article-1)
- A "context" file containing authoritative sources or citations (default: /mnt/data/context-1)
  This can be raw text, pasted citations, URLs, or structured JSON. The model will use this
  as the citation ground truth.

Outputs
-------
- fact_checked_article.md
- fact_check_report.json
- (optional) artifacts/ with saved/loaded DSPy program states

How to run
----------
1) Install DSPy 3.0.3 and set your LLM:
   >>> import dspy
   >>> dspy.settings.configure(lm=dspy.OpenAI(model="gpt-4o-mini"))   # example; use your provider

2) Run this script:
   $ python fact_checker_one_call.py --article /mnt/data/article-1 --context /mnt/data/context-1

3) (Optional) Run with GEPA optimization (few examples recommended):
   $ python fact_checker_one_call.py --optimize --train /path/to/train_dir --dev /path/to/dev_dir

Notes
-----
- This is a "single-LLM-call" program by design. The DSPy Module contains exactly one dspy.Predict
  call that returns *both* the revised article and the change report in a structured block.
- If you prefer a more conservative approach, you can enable two-stage mode via the CLI flag
  --two_stage, which still reduces calls relative to a 4-call pipeline.
"""

import os
import re
import json
import argparse
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Callable, Optional

import dspy
from dspy_factory import get_openrouter_model, DspyModelConfig
from pydantic import BaseModel, Field

import mlflow
from datetime import datetime

# ---------------
# Utility helpers
# ---------------


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def write_text(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def extract_sentences_with_citations(article: str) -> List[str]:
    """
    Extract sentences that contain existing citations in [CITED TEXT](URL) format.
    """
    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", article.strip())
    cited_sentences = []

    for sentence in sentences:
        # Look for citations in format [CITED TEXT](URL)
        if re.search(r"\[([^\]]+)\]\(https?://[^)]+\)", sentence):
            cited_sentences.append(sentence.strip())

    return cited_sentences


def extract_uncited_factual_sentences(article: str) -> List[str]:
    """
    Extract sentences with uncited factual content (numbers, percentages, quotes, dates).
    """
    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", article.strip())
    uncited_factual = []

    for sentence in sentences:
        # Skip if already has citation
        if re.search(r"\[([^\]]+)\]\(https?://[^)]+\)", sentence):
            continue

        # Check for factual content patterns
        has_factual_content = False

        # Numbers and percentages
        if re.search(r"\d+(\.\d+)?\s*%", sentence):
            has_factual_content = True
        # Specific numbers (but not years in isolation)
        elif re.search(
            r"\b\d+(\.\d+)?\s*(km|Gbps|GB|MB|TB|million|billion|thousand)\b",
            sentence,
            re.IGNORECASE,
        ):
            has_factual_content = True
        # Years (4 digits)
        elif re.search(r"\b(19|20)\d{2}\b", sentence):
            has_factual_content = True
        # Currency amounts
        elif re.search(r"\$\d+", sentence):
            has_factual_content = True
        # Quoted text (potential quotes from sources)
        elif re.search(r'"[^"]{10,}"', sentence):
            has_factual_content = True
        # Specific claims with definitive language
        elif re.search(
            r"\b(increased|decreased|reduced|improved|achieved|delivered|spans|reports?)\b.*\b\d+",
            sentence,
            re.IGNORECASE,
        ):
            has_factual_content = True

        if has_factual_content:
            uncited_factual.append(sentence.strip())

    return uncited_factual


def looks_like_citation(s: str) -> bool:
    """
    Heuristic check for inline citation markers.
    This is NOT authoritative, but is useful for guiding optimization metrics.
    """
    patterns = [
        r"\[.*?\]\(https?://\S+\)",
    ]
    return any(re.search(p, s) for p in patterns)


def factual_trigger(s: str) -> bool:
    """
    Very rough heuristic: a sentence is 'likely factual' if it contains numbers,
    years, percentages, currency, or definitive claims with specific patterns.
    """
    if re.search(r"\d{4}", s):  # years
        return True
    if re.search(r"\d+(\.\d+)?\s*%|\$\d+", s):
        return True
    # More specific patterns for factual claims - avoid common opinion phrases
    if re.search(r"\b(was|were|has|have|had)\b", s, re.IGNORECASE):
        return True
    # Only trigger on "is/are" if not in common opinion phrases
    if re.search(r"\b(is|are)\b", s, re.IGNORECASE):
        # Exclude common opinion patterns
        if not re.search(
            r"\b(just|think|believe|feel|opinion|seems?|appears?)\b", s, re.IGNORECASE
        ):
            return True
    return False


def simple_fact_coverage_metric(markdown: str) -> float:
    """
    Measures the fraction of 'factual' sentences that either have a citation marker
    or appear de-fanged/generalized (no numbers/years).
    """
    sents = re.split(r"(?<=[.!?])\s+", markdown.strip())
    if not sents:
        return 1.0
    factual = [s for s in sents if factual_trigger(s)]
    if not factual:
        return 1.0
    covered = 0
    for s in factual:
        if looks_like_citation(s):
            covered += 1
        else:
            # Consider it 'covered' if it no longer contains strong factual anchors
            if not re.search(r"\d", s):
                covered += 1
    return covered / max(1, len(factual))


# -----------------------
# Single-call DSPy design
# -----------------------


class ChangeRecord(BaseModel):
    original: str
    updated: str
    reason: str
    citation: Optional[str]


# ==========================================================================
# OUTPUT MODEL FOR INTEGRATION
# ==========================================================================


class FactCheckOutput(BaseModel):
    """Simple fact-check output for integration."""

    revised_article: str = Field(
        ..., description="Article with citations validated and corrected"
    )
    fact_check_passed: bool = Field(
        ..., description="Whether fact-checking passed without needing changes"
    )
    summary_feedback: str = Field(..., description="Summary of fact-checking results")
    changes_made: List[ChangeRecord] = Field(
        default_factory=list, description="List of changes made to the article"
    )


class FactCheckRewriteSig(dspy.Signature):
    """Multi-step fact-checking algorithm in a single DSPy call. Analyze the article systematically:

    STEP 1: Extract sentences with existing citations in format [CITED TEXT](URL)
    STEP 2: Extract sentences with uncited factual content (numbers, percentages, quotes, dates)
    STEP 3: For each extracted sentence, validate against context using chain-of-thought reasoning:
        - For cited sentences: verify citation accuracy and relevance
        - For uncited factual sentences: find supporting citations or generalize content
    STEP 4: Apply string replacements to update the article
    STEP 5: Generate comprehensive change report

    When validation fails, remove specific numbers/dates/quotes and create generalized replacement sentences.
    Preserve author's voice and intent. Use context format [CITATION TEXT](URL) for new citations.
    Output format for citations: [CITED TEXT](URL)
    """

    article = dspy.InputField(
        desc="Original markdown article to fact-check and rewrite."
    )
    context = dspy.InputField(
        desc="Authoritative sources in format [CITATION TEXT](URL). Use ONLY these sources for citations."
    )
    cited_sentences = dspy.InputField(
        desc="Sentences with existing citations extracted from article."
    )
    uncited_factual_sentences = dspy.InputField(
        desc="Sentences with uncited factual content extracted from article."
    )
    style_guidelines = dspy.InputField(
        desc="Constraints about tone, style, or formatting. Keep it short.",
        default="Keep voice, be faithful, cite rigorously.",
    )
    revised_article = dspy.OutputField(
        desc="The fully fact-checked markdown article with validated citations and generalized unsupported claims."
    )
    change_report: List[ChangeRecord] = dspy.OutputField(
        desc="A list of change records documenting what was modified with detailed reasoning"
    )


class FactChecker(dspy.Module):
    def __init__(self, models: Dict[str, DspyModelConfig]):
        super().__init__()
        self.models = models
        self.predict = dspy.Predict(FactCheckRewriteSig)

    def forward(
        self,
        article_text: str,
        context_content: str,
    ) -> dspy.Prediction:
        """
        Perform comprehensive fact-checking on an article.

        Args:
            article_text: The article text to fact-check
            context_content: Available context with inline citations

        Returns:
            dspy.Prediction containing FactCheckOutput
        """
        # Step 1: Extract sentences with existing citations
        cited_sentences = extract_sentences_with_citations(article_text)

        # Step 2: Extract sentences with uncited factual content
        uncited_factual_sentences = extract_uncited_factual_sentences(article_text)

        # Convert lists to formatted strings for DSPy input
        cited_sentences_str = (
            "\n".join([f"- {s}" for s in cited_sentences])
            if cited_sentences
            else "None found"
        )
        uncited_factual_str = (
            "\n".join([f"- {s}" for s in uncited_factual_sentences])
            if uncited_factual_sentences
            else "None found"
        )

        # Step 3-5: Single DSPy call with extracted sentence analysis
        with dspy.context(lm=self.models["judge"].dspy_lm):
            pred = self.predict(
                article=article_text,
                context=context_content,
                cited_sentences=cited_sentences_str,
                uncited_factual_sentences=uncited_factual_str,
                style_guidelines="Keep voice, be faithful, cite rigorously.",
            )

        # Analyze results
        changes_made = pred.change_report
        no_changes = len(changes_made) == 0

        if no_changes:
            summary = "✅ All citations verified and no factual issues found."
        else:
            summary = f"🔍 Made {len(changes_made)} fact-checking corrections"

        output = FactCheckOutput(
            revised_article=pred.revised_article,
            fact_check_passed=no_changes,
            summary_feedback=summary,
            changes_made=changes_made,
        )

        return dspy.Prediction(output=output)


# ------------------------------
# Optional: Two-stage DSPy flow
# ------------------------------


class AnalyzeAndRewriteSig(dspy.Signature):
    """Stage 1: Analyze claims and propose concrete edits with citations or generalizations.
    Return a JSON with keys 'edits' (list) and 'notes' (str).
    """

    article = dspy.InputField()
    context = dspy.InputField()
    analysis_json = dspy.OutputField()


class ApplyEditsSig(dspy.Signature):
    """Stage 2: Apply a given JSON of edits to the article, and format a final change report JSON."""

    article = dspy.InputField()
    analysis_json = dspy.InputField()
    revised_article = dspy.OutputField()
    change_report_json = dspy.OutputField()


class TwoStageFactChecker(dspy.Module):
    def __init__(self):
        super().__init__()
        self.analyze = dspy.Predict(AnalyzeAndRewriteSig)
        self.apply = dspy.Predict(ApplyEditsSig)

    def forward(self, article: str, context: str):
        analysis = self.analyze(article=article, context=context)
        applied = self.apply(article=article, analysis_json=analysis.analysis_json)
        return applied


# ------------------------------
# LM Validation and GEPA optimization
# ------------------------------


def validate_lm_configuration():
    """Validate that DSPy LM is properly configured."""
    if dspy.settings.lm is None:
        raise ValueError("No LM configured. Please set dspy.settings.configure(lm=...)")

    # Test basic functionality with a simple signature
    try:

        class TestSig(dspy.Signature):
            """Simple test signature for LM validation."""

            input = dspy.InputField()
            output = dspy.OutputField()

        test_pred = dspy.Predict(TestSig)
        # We don't actually call it to avoid API costs, just validate it can be created
        return True
    except Exception as e:
        raise ValueError(f"LM configuration test failed: {e}")


def load_pairs_from_dir(root: str) -> List[Tuple[str, str]]:
    """
    Load (article, context) pairs from a directory.
    We accept file pairs like article-*.md + context-* (any extension) with matching numeric suffixes.
    """
    if not root or not os.path.isdir(root):
        return []
    # Gather candidates
    arts = {}
    ctxs = {}
    for fn in os.listdir(root):
        path = os.path.join(root, fn)
        if not os.path.isfile(path):
            continue
        m = re.match(r"(article)-(\d+)(\.\w+)?$", fn)
        if m:
            idx = m.group(2)
            arts[idx] = path
        m2 = re.match(r"(context)-(\d+)(\.\w+)?$", fn)
        if m2:
            idx = m2.group(2)
            ctxs[idx] = path
    pairs = []
    for idx, apath in arts.items():
        cpath = ctxs.get(idx)
        if cpath:
            pairs.append((read_text(apath), read_text(cpath)))
    return pairs


@dataclass
class Example:
    article: str
    context: str
    gold_markdown: str = ""  # optional


def build_trainset(pairs: List[Tuple[str, str]]) -> List[Example]:
    exs = []
    for art, ctx in pairs:
        exs.append(Example(article=art, context=ctx))
    return exs


def quality_metric(example, pred, trace=None, pred_name=None, pred_trace=None):
    """
    Enhanced metric for GEPA optimization that returns score and feedback.
    This follows the correct DSPy 3.0.3 GEPA metric signature with all required parameters.
      - 60% weight: coverage of factual sentences with citations/generalization.
      - 40% weight: JSON parseability of change report.
    """
    try:
        # Validate prediction structure
        if not hasattr(pred, "revised_article") or not hasattr(
            pred, "change_report_json"
        ):
            return dspy.Prediction(score=0.0, feedback="Missing required output fields")

        score = 0.0
        feedback_parts = []

        try:
            md = pred.revised_article
            rep = pred.change_report_json
        except Exception as e:
            feedback_parts.append(f"Error accessing prediction fields: {e}")
            return dspy.Prediction(score=0.0, feedback="; ".join(feedback_parts))

        # coverage
        cov = simple_fact_coverage_metric(md)
        score += 0.6 * cov
        feedback_parts.append(f"Fact coverage: {cov:.2f}")

        # JSON validity + minimal structure
        try:
            arr = json.loads(rep)
            if isinstance(arr, list):
                # bonus for non-empty reasonable entries
                if len(arr) > 0 and all(isinstance(x, dict) for x in arr):
                    score += 0.4
                    feedback_parts.append("Valid JSON change report with entries")
                else:
                    score += 0.2
                    feedback_parts.append(
                        "Valid JSON structure but empty or invalid entries"
                    )
            else:
                score += 0.0
                feedback_parts.append("JSON is not a list")
        except Exception as e:
            score += 0.0
            feedback_parts.append(f"Invalid JSON: {e}")

        # cap to [0,1]
        score = max(0.0, min(1.0, score))
        feedback = "; ".join(feedback_parts)

        return dspy.Prediction(score=score, feedback=feedback)

    except Exception as e:
        return dspy.Prediction(
            score=0.0, feedback=f"Metric evaluation failed: {str(e)}"
        )


def run_gepa_optimization(
    trainset: List[Example],
    devset: List[Example],
    two_stage: bool = False,
    models: Dict[str, DspyModelConfig] = None,
):
    """
    Optimize using DSPy 3.0.3 GEPA with correct parameters and error handling.
    """
    if models is None:
        raise ValueError("models parameter is required for FactChecker initialization")
    program = TwoStageFactChecker() if two_stage else FactChecker(models)

    # Build DSPy examples in the expected format
    dspy_train = [
        dspy.Example(article=ex.article, context=ex.context).with_inputs(
            "article", "context"
        )
        for ex in trainset
    ]
    dspy_dev = (
        [
            dspy.Example(article=ex.article, context=ex.context).with_inputs(
                "article", "context"
            )
            for ex in devset
        ]
        if devset
        else None
    )

    # GEPA optimizer with DSPy 3.0.3 correct implementation
    try:
        # Use GEPA with correct parameters based on documentation
        # Note: Type annotation suppressed - function signature is correct per DSPy docs
        optimizer = dspy.GEPA(
            metric=quality_metric,  # type: ignore[arg-type]
            auto="light",  # Can be "light", "medium", or "heavy"
            num_threads=4,
            track_stats=True,
        )
        compiled = optimizer.compile(
            student=program, trainset=dspy_train, valset=dspy_dev
        )
        return compiled
    except Exception as e:
        print(f"[ERROR] GEPA optimization failed: {e}")
        print("[INFO] Falling back to unoptimized program")
        return program  # Return unoptimized program as fallback


# --------------
# Main CLI
# --------------


def resolve_model(
    model_name: str, default_model: str, default_constant: str, temp: float = 0.0
) -> DspyModelConfig:
    """
    Resolve a model using cascading fallback logic:
    1. Try get_openrouter_model(model_name)
    2. If None, try get_openrouter_model(default_model)
    3. If None, try get_openrouter_model(default_constant)
    4. If None, raise appropriate error

    Args:
        model_name: The primary model to try
        default_model: The fallback model from --model argument
        default_constant: The constant DEFAULT_MODEL_NAME

    Returns:
        DspyModelConfig with resolved model configuration

    Raises:
        RuntimeError: If no models can be resolved
    """
    # Try the primary model first
    model_config = get_openrouter_model(model_name, temp=temp)
    if model_config is not None:
        return model_config

    print(
        f"⚠️  Model '{model_name}' not found, falling back to default model '{default_model}'"
    )

    # Try the default model
    model_config = get_openrouter_model(default_model)
    if model_config is not None:
        return model_config

    print(
        f"⚠️  Default model '{default_model}' not found, falling back to constant '{default_constant}'"
    )

    # Try the constant default
    model_config = get_openrouter_model(default_constant)
    if model_config is not None:
        return model_config

    # If all fail, raise an error
    raise RuntimeError(
        f"❌ Unable to resolve any model. Tried:\n"
        f"  1. Primary model: '{model_name}'\n"
        f"  2. Default model: '{default_model}'\n"
        f"  3. Constant model: '{default_constant}'\n"
        f"Please check your OpenRouter API key and model names."
    )


def main():

    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    mlflow.set_experiment(f"DSPy One Fact {current_time}")
    mlflow.dspy.autolog()  # type: ignore # Automatically log DSPy runs to MLflow

    DEFAULT_MODEL_NAME = "moonshotai/kimi-k2:free"
    JUDGE_MODEL_NAME = "deepseek/deepseek-r1-0528:free"
    DEFAULT_MODEL_NAME = "moonshotai/kimi-k2:free"
    JUDGE_MODEL_NAME = "google/gemini-2.5-flash"

    resolved_judge = resolve_model(
        JUDGE_MODEL_NAME, DEFAULT_MODEL_NAME, DEFAULT_MODEL_NAME
    )

    models = {
        "judge": resolved_judge,
    }
    dspy.configure(lm=resolved_judge.dspy_lm)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--article",
        default="dev/article-1.md",
        help="Path to markdown article input",
    )
    parser.add_argument(
        "--context", default="dev/context-1.txt", help="Path to context/sources text"
    )
    parser.add_argument(
        "--out_dir", default="./one_call_results", help="Where to write outputs"
    )
    parser.add_argument(
        "--two_stage",
        action="store_true",
        help="Use a 2-call program (still fewer than 4)",
    )
    parser.add_argument(
        "--optimize", action="store_true", help="Run GEPA optimization before execution"
    )
    parser.add_argument(
        "--train",
        default=None,
        help="Directory with article-*/context-* pairs for training",
    )
    parser.add_argument(
        "--dev",
        default=None,
        help="Directory with article-*/context-* pairs for development",
    )
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # Validate LM configuration when optimization is requested
    if args.optimize:
        try:
            validate_lm_configuration()
            print("[INFO] LM configuration validated successfully")
        except ValueError as e:
            print(f"[ERROR] {e}")
            return 1

    # You must configure your LM outside or here. Example:
    # dspy.settings.configure(lm=dspy.OpenAI(model="gpt-4o-mini"))
    if dspy.settings.lm is None:
        print(
            "[WARN] No LM configured in dspy.settings. Please configure your provider before running."
        )
        print("Example: dspy.settings.configure(lm=dspy.OpenAI(model='gpt-4o-mini'))")
        # We proceed anyway so the script is self-contained.

    article = read_text(args.article)
    context = read_text(args.context)

    # Check for saved program
    saved_program_path = os.path.join(
        args.out_dir, "artifacts", "fact_checker_program.json"
    )
    program = None

    if not args.optimize and os.path.exists(saved_program_path):
        try:
            if args.two_stage:
                program = TwoStageFactChecker()
            else:
                program = FactChecker(models)
            program.load(saved_program_path)
            print(f"[INFO] Loaded saved program from {saved_program_path}")
        except Exception as e:
            print(f"[WARN] Could not load saved program: {e}")
            program = None

    # Optionally optimize or create new program
    if args.optimize:
        train_pairs = (
            load_pairs_from_dir(args.train) if args.train else [(article, context)]
        )
        dev_pairs = load_pairs_from_dir(args.dev) if args.dev else []
        trainset = build_trainset(train_pairs)
        devset = build_trainset(dev_pairs) if dev_pairs else []
        program = run_gepa_optimization(
            trainset, devset, two_stage=args.two_stage, models=models
        )
    else:
        program = TwoStageFactChecker() if args.two_stage else FactChecker(models)

    # Run the program (ONE CALL in the default OneCallFactChecker case)
    pred = program(article=article, context=context)

    # Persist outputs
    out_article = os.path.join(args.out_dir, "fact_checked_article.md")
    out_report = os.path.join(args.out_dir, "fact_check_report.json")
    write_text(out_article, pred.revised_article)
    write_text(out_report, pred.change_report_json)

    # Save the compiled program for reuse
    try:
        os.makedirs(os.path.join(args.out_dir, "artifacts"), exist_ok=True)
        program.save(
            os.path.join(args.out_dir, "artifacts", "fact_checker_program.json"),
            save_program=False,
        )
    except Exception as e:
        print(f"[WARN] Could not save DSPy program: {e}")

    print(f"[OK] Wrote: {out_article}")
    print(f"[OK] Wrote: {out_report}")


if __name__ == "__main__":
    main()
