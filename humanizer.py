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
