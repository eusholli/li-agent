#!/usr/bin/env python3
"""
LinkedIn Article Scoring Criteria

Contains the scoring criteria definitions and CriteriaExtractor for generating
scoring-aware prompts. No LLM scoring is performed here — the criteria are
embedded into the generation prompt so the LLM optimizes for them directly.
"""

from typing import Dict, List, Tuple, Optional
from models import FactCheckResult  # noqa: keep for fc_oc_v2 compatibility

# ==========================================================================
# SCORING CRITERIA DEFINITIONS (180 points total)
# ==========================================================================

SCORING_CRITERIA = {
    "First-Order Thinking": [
        {
            "question": "Does the article break down complex problems into fundamental components rather than relying on analogies or existing solutions?",
            "points": 15,
            "scale": {
                1: "Relies heavily on analogies and surface-level comparisons",
                3: "Some attempt to examine fundamentals but inconsistent",
                5: "Consistently breaks problems down to basic principles and rebuilds understanding",
            },
        },
        {
            "question": "Does it challenge conventional wisdom by examining root assumptions and rebuilding from basic principles?",
            "points": 15,
            "scale": {
                1: "Accepts conventional wisdom without question",
                3: "Questions some assumptions but doesn't dig deep",
                5: "Systematically challenges assumptions and rebuilds from first principles",
            },
        },
        {
            "question": "Does it avoid surface-level thinking and instead dig into the 'why' behind commonly accepted ideas?",
            "points": 15,
            "scale": {
                1: "Stays at surface level with obvious observations",
                3: "Some deeper analysis but not consistently applied",
                5: "Consistently probes deeper into root causes and fundamental 'why' questions",
            },
        },
    ],
    "Strategic Deconstruction & Synthesis": [
        {
            "question": "Does it deconstruct a complex system (a market, a company's strategy, a technology) into its fundamental components and incentives?",
            "points": 20,
            "scale": {
                1: "Describes the system at a surface level without dissecting it.",
                3: "Identifies some components but doesn't fully explain their interactions or underlying incentives.",
                5: "Systematically breaks down the system into its core parts and clearly explains how they interact.",
            },
        },
        {
            "question": "Does it synthesize disparate information (e.g., history, financial data, product strategy, quotes) into a single, coherent thesis?",
            "points": 20,
            "scale": {
                1: "Presents information as a list of disconnected facts.",
                3: "Attempts to connect different pieces of information, but the central thesis is weak or unclear.",
                5: "Masterfully weaves together diverse sources into a strong, unified, and memorable argument.",
            },
        },
        {
            "question": "Does it identify second- and third-order effects, explaining the cascading 'so what?' consequences of a core idea or event?",
            "points": 15,
            "scale": {
                1: "Focuses only on the immediate, first-order effects.",
                3: "Mentions some downstream effects but doesn't explore their full implications.",
                5: "Clearly explains the chain reaction of consequences, showing deep understanding of the system's dynamics.",
            },
        },
        {
            "question": "Does it introduce a durable framework or mental model that helps explain the system and is transferable to other contexts?",
            "points": 15,
            "scale": {
                1: "Offers opinions without a clear underlying framework.",
                3: "Uses existing frameworks but doesn't introduce a new or refined mental model.",
                5: "Provides a powerful, memorable, and reusable mental model for understanding the topic.",
            },
        },
        {
            "question": "Does it explain the fundamental 'why' behind events, rather than just describing the 'what'?",
            "points": 5,
            "scale": {
                1: "Reports on events without providing deep causal analysis.",
                3: "Offers some explanation for the 'why' but it remains at a surface level.",
                5: "Consistently digs beneath the surface to reveal the core strategic, economic, or historical drivers.",
            },
        },
    ],
    "Hook & Engagement": [
        {
            "question": "Does the opening immediately grab attention with curiosity, emotion, or urgency?",
            "points": 5,
            "scale": {
                1: "Bland opening; no reason to keep reading",
                3: "Somewhat interesting but predictable",
                5: "Strong hook that makes reading irresistible",
            },
        },
        {
            "question": "Does the intro clearly state why this matters to the reader in the first 3 sentences?",
            "points": 5,
            "scale": {
                1: "Relevance is unclear",
                3: "Relevance implied but not explicit",
                5: "Clear, personal relevance to target audience immediately",
            },
        },
    ],
    "Storytelling & Structure": [
        {
            "question": "Is the article structured like a narrative (problem -> tension -> resolution -> takeaway)?",
            "points": 5,
            "scale": {
                1: "Disjointed list of points",
                3: "Some flow, but transitions are weak",
                5: "Smooth arc with a natural flow that keeps readers moving",
            },
        },
        {
            "question": "Are there specific, relatable examples or anecdotes?",
            "points": 5,
            "scale": {
                1: "Generic statements with no real-life grounding",
                3: "Some examples, but not vivid",
                5: "Memorable examples that make points stick",
            },
        },
    ],
    "Authority & Credibility": [
        {
            "question": "Are claims backed by data, research, or credible sources?",
            "points": 5,
            "scale": {
                1: "No evidence given",
                3: "Some supporting info, but patchy",
                5: "Strong, credible evidence throughout",
            },
        },
        {
            "question": "Does the article demonstrate unique experience or perspective?",
            "points": 5,
            "scale": {
                1: "Generic, could be written by anyone",
                3: "Some personal insight but not distinct",
                5: "Clear, lived authority shines through",
            },
        },
    ],
    "Idea Density & Clarity": [
        {
            "question": "Is there one clear, central idea driving the piece?",
            "points": 5,
            "scale": {
                1: "Multiple competing ideas; scattered focus",
                3: "Mostly one theme but diluted by tangents",
                5: "Laser-focused on one strong idea",
            },
        },
        {
            "question": "Is every sentence valuable (no filler or fluff)?",
            "points": 5,
            "scale": {
                1: "Lots of repetition or empty words",
                3: "Mostly relevant with occasional filler",
                5: "Concise, high-value throughout",
            },
        },
    ],
    "Reader Value & Actionability": [
        {
            "question": "Does the reader walk away with practical, actionable insights?",
            "points": 5,
            "scale": {
                1: "Vague advice, nothing to act on",
                3: "Some useful tips but not clearly actionable",
                5: "Concrete steps or takeaways that can be applied immediately",
            },
        },
        {
            "question": "Are lessons transferable beyond the example given?",
            "points": 5,
            "scale": {
                1: "Only relevant in a narrow context",
                3: "Partially transferable",
                5: "Clearly relevant across multiple scenarios",
            },
        },
    ],
    "Call to Connection": [
        {
            "question": "Does it end with a thought-provoking question or reflection prompt?",
            "points": 5,
            "scale": {
                1: "No CTA or a generic 'What do you think?'",
                3: "Somewhat engaging but generic",
                5: "Strong, specific prompt that sparks dialogue",
            },
        },
        {
            "question": "Does it use inclusive, community-building language ('we,' 'us,' shared goals)?",
            "points": 5,
            "scale": {
                1: "Detached, academic tone",
                3: "Some warmth but not consistent",
                5: "Warm, inclusive tone throughout",
            },
        },
    ],
}


# ==========================================================================
# CRITERIA EXTRACTOR
# ==========================================================================


class CriteriaExtractor:
    """
    Extracts and formats scoring criteria for article generation prompts.
    The criteria are embedded in the generation prompt so the LLM optimizes
    for them directly — no separate scoring step needed.
    """

    def __init__(self, min_length: int, max_length: int):
        self.criteria = SCORING_CRITERIA
        self.min_length = min_length
        self.max_length = max_length
        self._category_weights: Optional[Dict[str, int]] = None

    def get_category_weights(self) -> Dict[str, int]:
        if self._category_weights is None:
            self._category_weights = {
                cat: sum(c.get("points", 5) for c in criteria)
                for cat, criteria in self.criteria.items()
            }
        return self._category_weights

    def get_total_possible_score(self) -> int:
        return sum(self.get_category_weights().values())

    def get_criteria_for_generation(self) -> str:
        """Format criteria for the article generation prompt."""
        lines = [
            "SCORING CRITERIA FOR ARTICLE GENERATION:",
            "Your article will be evaluated on these criteria:\n",
            f"**Article Length** (200 points total):",
            f"As the top priority the article must be between {self.min_length} and {self.max_length} words in length.",
            "",
        ]

        weights = self.get_category_weights()
        for category, total_points in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"**{category}** ({total_points} points total):")
            for criterion in self.criteria[category]:
                points = criterion.get("points", 5)
                lines.append(f"  * ({points} pts) {criterion['question']}")
                if points >= 15:
                    scale = criterion.get("scale", {})
                    if scale:
                        lines.append(f"    Scale: {scale.get(5, 'Excellent performance')}")
            lines.append("")

        lines.extend([
            "OPTIMIZATION PRIORITIES:",
            "1. Article length is most important (200 points)",
            "2. Focus heavily on Strategic Deconstruction & Synthesis (75 points)",
            "3. Emphasize First-Order Thinking (45 points)",
            "4. Ensure strong engagement and professional authority",
        ])

        return "\n".join(lines)
