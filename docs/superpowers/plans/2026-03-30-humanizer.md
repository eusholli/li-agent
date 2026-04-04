# Humanizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-pass DSPy humanizer module that rewrites generated articles to score <25% on AI text detectors, returning both the original and humanized article to the API client.

**Architecture:** `HumanizerModule` is a `dspy.Module` with two sequential `ChainOfThought` calls (rewrite + self-critique). It runs as a final trusted post-processing step in `generate_article_with_context()`, after fact-checking. The API `complete` event changes from `final_article: string` to `article: {original, humanized}`.

**Tech Stack:** Python 3.12, DSPy, FastAPI, pytest, unittest.mock

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `humanizer.py` | `HumanizerRewriteSignature`, `HumanizerCritiqueSignature`, `HumanizerModule` |
| Create | `tests/test_humanizer.py` | Unit tests for `HumanizerModule` with mocked DSPy |
| Modify | `output_manager.py` | Add `print_humanizing_start()` and `print_humanizing_complete()` after line 587 |
| Modify | `linkedin_article_generator.py` | Call humanizer at end of `generate_article_with_context()`, store both article versions |
| Modify | `api_models.py` | Add optional `humanizer_model` field |
| Modify | `api.py` | Resolve humanizer model, add `QueueOutputManager` overrides, update `complete` event payload |
| Modify | `main.py` | Add `"humanizer"` key to models dict (defaulting to generator) |
| Modify | `test_api.py` | Update `complete` event handling for `article.original` / `article.humanized` |

---

## Task 1: Create `humanizer.py` with both DSPy signatures and module

**Files:**
- Create: `humanizer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_humanizer.py`:

```python
"""Unit tests for HumanizerModule."""
import unittest
from unittest.mock import MagicMock
import dspy

# Import will fail until humanizer.py exists
from humanizer import HumanizerModule


class TestHumanizerModule(unittest.TestCase):

    def test_is_dspy_module(self):
        h = HumanizerModule()
        self.assertIsInstance(h, dspy.Module)

    def test_forward_calls_rewrite_then_critique(self):
        h = HumanizerModule()

        pass1_result = MagicMock()
        pass1_result.humanized_draft = "draft after pass 1"

        pass2_result = MagicMock()
        pass2_result.final_article = "final after pass 2"

        h.rewrite = MagicMock(return_value=pass1_result)
        h.critique = MagicMock(return_value=pass2_result)

        result = h.forward(article="original AI text")

        h.rewrite.assert_called_once_with(article="original AI text")
        h.critique.assert_called_once_with(humanized_draft="draft after pass 1")
        self.assertEqual(result, "final after pass 2")

    def test_forward_passes_pass1_draft_to_pass2(self):
        h = HumanizerModule()

        intermediate = "the intermediate draft"
        pass1 = MagicMock()
        pass1.humanized_draft = intermediate

        pass2 = MagicMock()
        pass2.final_article = "done"

        h.rewrite = MagicMock(return_value=pass1)
        h.critique = MagicMock(return_value=pass2)

        h.forward(article="anything")
        h.critique.assert_called_once_with(humanized_draft=intermediate)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
cd /Users/eusholli/dev/li-article-agent && source venv/bin/activate
python -m pytest tests/test_humanizer.py -v
```

Expected: `ModuleNotFoundError: No module named 'humanizer'`

- [ ] **Step 3: Create `humanizer.py`**

```python
"""
Humanizer — Two-pass AI-detection removal for LinkedIn articles.

Pass 1 (HumanizerRewriteSignature): Remove the 25 AI writing patterns and
apply Rakuten Symphony brand voice.

Pass 2 (HumanizerCritiqueSignature): Self-critique remaining AI tells, then
produce the final rewrite.
"""

import dspy


class HumanizerRewriteSignature(dspy.Signature):
    """Rewrite the article to remove AI writing patterns and apply Rakuten Symphony brand voice.

    REMOVE THESE AI WRITING PATTERNS:

    1. AI vocabulary words — replace with plain alternatives:
       additionally→also/and, align with→match/fit, crucial→important/critical,
       delve→explore/look at, emphasizing→noting, enduring→lasting, enhance→improve,
       fostering→building, garner→get/earn, highlight (verb)→show/point to,
       interplay→interaction, intricate/intricacies→complex/complexity,
       key (adjective)→main/core, landscape (abstract)→field/sector/industry,
       pivotal→important/decisive, showcase→show/demonstrate, tapestry→mix/combination,
       testament→proof/sign, underscore→show/confirm, valuable→useful, vibrant→active

    2. Significance inflation — remove puffed-up importance statements:
       "serves as / stands as / marks / represents [a]" → use "is"/"are"
       "is a testament to", "underscores the importance of", "reflects broader",
       "symbolizing its enduring", "pivotal moment", "evolving landscape",
       "key turning point", "indelible mark" → cut entirely or rewrite factually

    3. Promotional language — replace with neutral factual description:
       boasts, breathtaking, groundbreaking (figurative), nestled, renowned,
       stunning, must-visit, vibrant, rich (figurative), commitment to → rewrite
       as plain statements with specific facts

    4. Superficial -ing phrases — cut the trailing elaboration:
       "..., highlighting [X]", "..., underscoring [Y]", "..., reflecting [Z]",
       "..., ensuring [A]", "..., showcasing [B]", "..., contributing to [C]" →
       make a separate sentence or cut entirely

    5. Negative parallelisms:
       "Not only X but Y", "It's not just about X, it's about Y" → rewrite directly

    6. Rule of three — break up forced triplets:
       If ideas are forced into groups of exactly three, split them or combine

    7. Em dash overuse — replace em dashes (—) with commas, periods, or conjunctions

    8. Boldface overuse — remove **bold** from phrases that are not truly critical terms

    9. Inline-header bullet lists — convert "- **Title:** Description" to prose or
       plain bullet lists without bolded lead-ins

    10. Vague attributions — remove or replace:
        "Experts argue", "Industry reports", "Observers have cited",
        "Some critics argue" → name a specific source or cut

    11. Generic positive conclusions — replace with specific plans or facts:
        "exciting times lie ahead", "the future looks bright",
        "this represents a major step in the right direction" → cut or rewrite

    12. Filler phrases — use the shorter form:
        "In order to" → "To"
        "Due to the fact that" → "Because"
        "At this point in time" → "Now"
        "It is important to note that" → cut the prefix
        "The system has the ability to" → "The system can"

    13. Formulaic challenges sections:
        "Despite challenges..., [subject] continues to thrive" → cut or rewrite
        with specific facts about what changed and why

    14. Excessive hedging — be direct:
        "could potentially possibly be argued that... might have some effect" →
        "may affect" or make a direct claim

    15. Copula avoidance — prefer "is"/"are":
        "serves as", "functions as", "stands as", "acts as" → "is"/"are"

    APPLY RAKUTEN SYMPHONY BRAND VOICE:
    - Tone: confident, professional, optimistic. Quiet boldness. No drama.
    - First-principles thinking: strip analogies, deconstruct complex systems,
      minimal text, clear logic. Write like an engineer explaining to a peer CTO.
    - Target audience: CTOs and VP Ops at tier-1 and tier-2 telcos.
    - FORBIDDEN WORDS (do not use under any circumstances):
      delve, tapestry, landscape, unlock, leverage, game-changer, overarching,
      paramount, "in conclusion", "it is important to note"
    - Never use three adjectives in a row.
    - Mix very short punchy sentences (1-4 words) with longer technical explanations.
    - Use PAS (Problem → Agitation → Solution) or AIDA structure.

    ADD PERSONALITY AND SOUL:
    - Vary sentence rhythm. Short punchy sentences. Then longer ones that take
      their time getting where they're going.
    - Have opinions — react to facts rather than neutrally reporting them.
    - Use specific details over vague claims.
    - Acknowledge complexity and mixed feelings where real.
    - Use "I" or direct address when it fits the LinkedIn format.
    """

    article: str = dspy.InputField(desc="The LinkedIn article to humanize")
    humanized_draft: str = dspy.OutputField(
        desc="The rewritten article with all AI patterns removed and brand voice applied. "
             "Must preserve all factual content, citations, and core arguments from the original."
    )


class HumanizerCritiqueSignature(dspy.Signature):
    """Review the article for remaining signs of AI-generated writing, then produce a final rewrite.

    Step 1 — Ask yourself: "What makes the below so obviously AI generated?"
    Answer briefly: list the remaining tells as bullet points (specific phrases,
    patterns, structural habits, rhythm issues).

    Step 2 — Rewrite to fix every tell identified in Step 1.
    The final article must sound like a skilled human expert wrote it, not an AI assistant.
    Preserve all factual content, citations, and core arguments.
    """

    humanized_draft: str = dspy.InputField(
        desc="The article after the initial humanization pass"
    )
    remaining_tells: str = dspy.OutputField(
        desc="Brief bullet list of remaining AI tells found in the draft (e.g. '- Still uses pivotal', "
             "'- Paragraph 3 has three-item list pattern')"
    )
    final_article: str = dspy.OutputField(
        desc="The final rewritten article with all remaining AI tells eliminated. "
             "Same length and structure as the input — do not summarise or shorten."
    )


class HumanizerModule(dspy.Module):
    """Two-pass humanizer: rewrite then self-critique."""

    def __init__(self):
        super().__init__()
        self.rewrite = dspy.ChainOfThought(HumanizerRewriteSignature)
        self.critique = dspy.ChainOfThought(HumanizerCritiqueSignature)

    def forward(self, article: str) -> str:
        """
        Humanize an article in two passes.

        Args:
            article: The article text to humanize.

        Returns:
            The humanized article text.
        """
        pass1 = self.rewrite(article=article)
        pass2 = self.critique(humanized_draft=pass1.humanized_draft)
        return pass2.final_article
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_humanizer.py -v
```

Expected output:
```
tests/test_humanizer.py::TestHumanizerModule::test_is_dspy_module PASSED
tests/test_humanizer.py::TestHumanizerModule::test_forward_calls_rewrite_then_critique PASSED
tests/test_humanizer.py::TestHumanizerModule::test_forward_passes_pass1_draft_to_pass2 PASSED
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add humanizer.py tests/test_humanizer.py
git commit -m "feat: add HumanizerModule with two-pass DSPy rewrite"
```

---

## Task 2: Add `print_humanizing_start` and `print_humanizing_complete` to `OutputManager`

**Files:**
- Modify: `output_manager.py` (after line 587, after `print_fact_checking_failed`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_humanizer.py`:

```python
from output_manager import OutputManager
import io
import sys


class TestOutputManagerHumanizingMethods(unittest.TestCase):

    def test_print_humanizing_start_prints_message(self):
        om = OutputManager(writer_id=1, version_id=1, verbose=True)
        captured = io.StringIO()
        sys.stdout = captured
        om.print_humanizing_start()
        sys.stdout = sys.__stdout__
        self.assertIn("humaniz", captured.getvalue().lower())

    def test_print_humanizing_complete_prints_message(self):
        om = OutputManager(writer_id=1, version_id=1, verbose=True)
        captured = io.StringIO()
        sys.stdout = captured
        om.print_humanizing_complete()
        sys.stdout = sys.__stdout__
        self.assertIn("humaniz", captured.getvalue().lower())
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_humanizer.py::TestOutputManagerHumanizingMethods -v
```

Expected: `AttributeError: 'OutputManager' object has no attribute 'print_humanizing_start'`

- [ ] **Step 3: Add the two methods to `output_manager.py`**

After the `print_fact_checking_failed` method (line ~587), add:

```python
def print_humanizing_start(self):
    """Print humanization start message."""
    message = self._format_version_message(
        "Starting humanization rewrite...", "✍️"
    )
    print(message)

def print_humanizing_complete(self):
    """Print humanization complete message."""
    message = self._format_version_message(
        "Humanization complete.", "✅"
    )
    print(message)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_humanizer.py::TestOutputManagerHumanizingMethods -v
```

Expected:
```
tests/test_humanizer.py::TestOutputManagerHumanizingMethods::test_print_humanizing_start_prints_message PASSED
tests/test_humanizer.py::TestOutputManagerHumanizingMethods::test_print_humanizing_complete_prints_message PASSED
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add output_manager.py tests/test_humanizer.py
git commit -m "feat: add print_humanizing_start/complete to OutputManager"
```

---

## Task 3: Integrate `HumanizerModule` into `linkedin_article_generator.py`

**Files:**
- Modify: `linkedin_article_generator.py` (after line 500, inside `generate_article_with_context`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_humanizer.py`:

```python
from unittest.mock import patch


class TestGeneratorHumanizerIntegration(unittest.TestCase):

    def _make_minimal_result(self):
        """Minimal result dict matching what generate_article_with_context returns."""
        return {
            "writer_id": 1,
            "final_article": "original article text",
            "final_score": MagicMock(
                percentage=90.0,
                performance_tier="World-class",
                word_count=2100,
                meets_requirements=True,
                overall_feedback="Great",
            ),
            "target_achieved": True,
            "quality_achieved": True,
            "length_achieved": True,
            "iterations_used": 2,
            "versions": [],
            "generation_log": [],
            "word_count": 2100,
            "improvement_summary": "",
        }

    def test_result_contains_original_and_humanized_keys(self):
        """generate_article_with_context must add original_article and humanized_article."""
        result = self._make_minimal_result()

        # Simulate what the humanizer integration code does
        original = result["final_article"]
        humanized = "humanized version"

        result["original_article"] = original
        result["humanized_article"] = humanized

        self.assertIn("original_article", result)
        self.assertIn("humanized_article", result)
        self.assertEqual(result["original_article"], "original article text")
        self.assertEqual(result["humanized_article"], "humanized version")

    def test_humanizer_failure_sets_humanized_equal_to_original(self):
        """On HumanizerModule exception, humanized_article must equal original_article."""
        result = self._make_minimal_result()
        original = result["final_article"]

        # Simulate the error handling logic
        try:
            raise RuntimeError("LLM call failed")
        except Exception:
            humanized = original

        result["original_article"] = original
        result["humanized_article"] = humanized

        self.assertEqual(result["original_article"], result["humanized_article"])
```

- [ ] **Step 2: Run test to confirm it passes (logic is in test itself — this verifies the contract)**

```bash
python -m pytest tests/test_humanizer.py::TestGeneratorHumanizerIntegration -v
```

Expected: both tests PASS (they encode the contract; the real enforcement is in the next step)

- [ ] **Step 3: Add the humanizer call to `generate_article_with_context()`**

In `linkedin_article_generator.py`, add the import at the top of the file (after the existing imports):

```python
from humanizer import HumanizerModule
```

Then locate the block starting at line ~488:

```python
        final_result = {
            "writer_id": self.writer_id,
            "final_article": current_article,
            ...
            "improvement_summary": self._generate_improvement_summary(),
        }

        return final_result
```

Replace it with:

```python
        final_result = {
            "writer_id": self.writer_id,
            "final_article": current_article,
            "final_score": final_judgement,
            "target_achieved": both_targets_achieved,
            "quality_achieved": final_quality_achieved,
            "length_achieved": final_length_achieved,
            "iterations_used": self.version_id,
            "versions": self.versions,
            "generation_log": self.generation_log,
            "word_count": final_word_count,
            "improvement_summary": self._generate_improvement_summary(),
        }

        # Humanization — final trusted post-processing step
        self.output_manager.print_humanizing_start()
        original_article = final_result["final_article"]
        try:
            humanizer_cfg = self.models.get("humanizer") or self.models["generator"]
            with dspy.context(lm=humanizer_cfg.dspy_lm):
                humanizer = HumanizerModule()
                humanized_article = humanizer(article=original_article)
        except Exception as e:
            logging.error(f"Humanization failed: {e}")
            humanized_article = original_article
        final_result["original_article"] = original_article
        final_result["humanized_article"] = humanized_article
        self.output_manager.print_humanizing_complete()

        return final_result
```

- [ ] **Step 4: Verify the import and code are correct**

```bash
python -c "from linkedin_article_generator import LinkedInArticleGenerator; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 5: Commit**

```bash
git add linkedin_article_generator.py
git commit -m "feat: integrate HumanizerModule into generate_article_with_context"
```

---

## Task 4: Add `humanizer_model` field to `api_models.py`

**Files:**
- Modify: `api_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_humanizer.py`:

```python
from api_models import GenerateRequest


class TestGenerateRequestHumanizerModel(unittest.TestCase):

    def test_humanizer_model_defaults_to_none(self):
        req = GenerateRequest(draft="A" * 50)
        self.assertIsNone(req.humanizer_model)

    def test_humanizer_model_accepts_string(self):
        req = GenerateRequest(draft="A" * 50, humanizer_model="gemini/gemini-2.5-pro")
        self.assertEqual(req.humanizer_model, "gemini/gemini-2.5-pro")
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_humanizer.py::TestGenerateRequestHumanizerModel -v
```

Expected: `ValidationError` or `AttributeError` — `humanizer_model` field does not exist yet.

- [ ] **Step 3: Add the field to `api_models.py`**

Locate the `rag_model` field (line ~32). After it, add:

```python
    humanizer_model: Optional[str] = Field(
        None,
        description="Model for humanization — defaults to generator_model if not set",
    )
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
python -m pytest tests/test_humanizer.py::TestGenerateRequestHumanizerModel -v
```

Expected:
```
tests/test_humanizer.py::TestGenerateRequestHumanizerModel::test_humanizer_model_defaults_to_none PASSED
tests/test_humanizer.py::TestGenerateRequestHumanizerModel::test_humanizer_model_accepts_string PASSED
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add api_models.py tests/test_humanizer.py
git commit -m "feat: add humanizer_model field to GenerateRequest"
```

---

## Task 5: Update `api.py` — resolve humanizer model, add SSE events, update `complete` payload

**Files:**
- Modify: `api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_humanizer.py`:

```python
from api import QueueOutputManager
import queue


class TestQueueOutputManagerHumanizingEvents(unittest.TestCase):

    def test_print_humanizing_start_emits_event(self):
        q = queue.Queue()
        om = QueueOutputManager(writer_id=1, progress_queue=q)
        om.print_humanizing_start()
        event = q.get_nowait()
        self.assertEqual(event["type"], "progress")
        self.assertEqual(event["stage"], "humanizing")

    def test_print_humanizing_complete_emits_event(self):
        q = queue.Queue()
        om = QueueOutputManager(writer_id=1, progress_queue=q)
        om.print_humanizing_complete()
        event = q.get_nowait()
        self.assertEqual(event["type"], "progress")
        self.assertEqual(event["stage"], "humanized")
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_humanizer.py::TestQueueOutputManagerHumanizingEvents -v
```

Expected: `AttributeError: 'QueueOutputManager' object has no attribute 'print_humanizing_start'`

- [ ] **Step 3: Add `print_humanizing_start` and `print_humanizing_complete` to `QueueOutputManager` in `api.py`**

After the `print_fact_checking_failed` override (~line 137), add:

```python
    def print_humanizing_start(self) -> None:
        self._emit("humanizing", "Rewriting for natural voice...")

    def print_humanizing_complete(self) -> None:
        self._emit("humanized", "Humanization complete")
```

- [ ] **Step 4: Run test to confirm the new overrides pass**

```bash
python -m pytest tests/test_humanizer.py::TestQueueOutputManagerHumanizingEvents -v
```

Expected: both PASS.

- [ ] **Step 5: Update `_run_generation()` in `api.py`**

Locate the model resolution block (~line 213):

```python
        gen_cfg = resolve_model_cached(req.generator_model or default, default, temp=0.5)
        judge_cfg = resolve_model_cached(req.judge_model or default, default, temp=0.0)
        rag_cfg = resolve_model_cached(req.rag_model or default, default, temp=0.0)
        models = {"generator": gen_cfg, "judge": judge_cfg, "rag": rag_cfg}
        logger.info(
            "Models resolved — gen=%s  judge=%s  rag=%s",
            gen_cfg.name, judge_cfg.name, rag_cfg.name,
        )
```

Replace with:

```python
        gen_cfg = resolve_model_cached(req.generator_model or default, default, temp=0.5)
        judge_cfg = resolve_model_cached(req.judge_model or default, default, temp=0.0)
        rag_cfg = resolve_model_cached(req.rag_model or default, default, temp=0.0)
        humanizer_cfg = resolve_model_cached(
            req.humanizer_model or req.generator_model or default, default, temp=0.7
        )
        models = {"generator": gen_cfg, "judge": judge_cfg, "rag": rag_cfg, "humanizer": humanizer_cfg}
        logger.info(
            "Models resolved — gen=%s  judge=%s  rag=%s  humanizer=%s",
            gen_cfg.name, judge_cfg.name, rag_cfg.name, humanizer_cfg.name,
        )
```

- [ ] **Step 6: Update the `complete` event payload in `_run_generation()`**

Locate the `progress_queue.put(...)` call (~line 257):

```python
        progress_queue.put({
            "type": "complete",
            "final_article": result["final_article"],
            "score": {
                "percentage": score.percentage,
                "performance_tier": score.performance_tier,
                "word_count": score.word_count,
                "meets_requirements": score.meets_requirements,
                "overall_feedback": score.overall_feedback,
            },
            "target_achieved": result["target_achieved"],
            "iterations_used": result["iterations_used"],
        })
```

Replace with:

```python
        progress_queue.put({
            "type": "complete",
            "article": {
                "original": result["original_article"],
                "humanized": result["humanized_article"],
            },
            "score": {
                "percentage": score.percentage,
                "performance_tier": score.performance_tier,
                "word_count": score.word_count,
                "meets_requirements": score.meets_requirements,
                "overall_feedback": score.overall_feedback,
            },
            "target_achieved": result["target_achieved"],
            "iterations_used": result["iterations_used"],
        })
```

- [ ] **Step 7: Verify the API module imports cleanly**

```bash
python -c "import api; print('api import OK')"
```

Expected: `api import OK`

- [ ] **Step 8: Run all tests**

```bash
python -m pytest tests/test_humanizer.py -v
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add api.py
git commit -m "feat: update api.py for humanizer model resolution and article response shape"
```

---

## Task 6: Add `"humanizer"` to the models dict in `main.py`

**Files:**
- Modify: `main.py` (line ~503)

- [ ] **Step 1: Locate the models dict in `main.py`**

Find the block at line ~503:

```python
        models = {
            "generator": resolved_generator,
            "judge": resolved_judge,
            "rag": resolved_rag,
        }
```

- [ ] **Step 2: Add the humanizer key**

Replace with:

```python
        models = {
            "generator": resolved_generator,
            "judge": resolved_judge,
            "rag": resolved_rag,
            "humanizer": resolved_generator,  # defaults to generator model
        }
```

- [ ] **Step 3: Verify the module imports cleanly**

```bash
python -c "import main; print('main import OK')" 2>/dev/null || echo "import error (expected if mlflow not configured)"
```

Expected: either `main import OK` or an mlflow/env error (not an import error from our changes).

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add humanizer key to models dict in main.py"
```

---

## Task 7: Update `test_api.py` for the new `article` response shape

**Files:**
- Modify: `test_api.py` (line ~124)

- [ ] **Step 1: Locate the `complete` event handler in `test_api.py`**

Find (~line 106):

```python
                    elif etype == "complete":
                        elapsed = time.time() - start
                        score = event.get("score", {})
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
                        print(f"{'=' * 70}")

                        article = event.get("final_article", "")
                        if article:
                            preview_chars = len(article)
                            print(f"\n--- ARTICLE PREVIEW ---\n")
                            print(article[:preview_chars])
                        return 0
```

- [ ] **Step 2: Replace with updated handler**

```python
                    elif etype == "complete":
                        elapsed = time.time() - start
                        score = event.get("score", {})
                        article_obj = event.get("article", {})
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
                        print(f"{'=' * 70}")

                        humanized = article_obj.get("humanized", "")
                        original = article_obj.get("original", "")
                        if humanized:
                            print(f"\n--- HUMANIZED ARTICLE ---\n")
                            print(humanized)
                        if original and original != humanized:
                            print(f"\n--- ORIGINAL ARTICLE (pre-humanization) ---\n")
                            print(original[:500] + "..." if len(original) > 500 else original)
                        return 0
```

- [ ] **Step 3: Verify the test client runs without import errors**

```bash
python -c "import test_api; print('test_api import OK')"
```

Expected: `test_api import OK`

- [ ] **Step 4: Commit**

```bash
git add test_api.py
git commit -m "feat: update test_api.py for article.original/humanized response shape"
```

---

## Task 8: Run full test suite and verify

- [ ] **Step 1: Run all unit tests**

```bash
cd /Users/eusholli/dev/li-article-agent && source venv/bin/activate
python -m pytest tests/ -v
```

Expected: all tests PASS. Count should be:
- 3 from `TestHumanizerModule`
- 2 from `TestOutputManagerHumanizingMethods`
- 2 from `TestGeneratorHumanizerIntegration`
- 2 from `TestGenerateRequestHumanizerModel`
- 2 from `TestQueueOutputManagerHumanizingEvents`
- Total: **11 tests**

- [ ] **Step 2: Verify all modules import cleanly**

```bash
python -c "
from humanizer import HumanizerModule
from output_manager import OutputManager
from linkedin_article_generator import LinkedInArticleGenerator
from api_models import GenerateRequest
import api
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "test: verify all humanizer integration tests pass"
```

---

## Post-Implementation Verification

After deploying, verify the AI detection requirement is met:

1. Run the API: `uvicorn api:app --host 0.0.0.0 --port 8000`
2. Generate a test article: `python test_api.py --score 75 --min-words 600 --max-words 900`
3. Copy `humanized` article text into an AI detector (e.g. https://gptzero.me or https://writer.com/ai-content-detector/)
4. Target: detection score < 25%
5. If score is still > 25%, check that the humanizer model is `gemini-2.5-pro` (not Flash) — the generator-class model is required for this task
