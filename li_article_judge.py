#!/usr/bin/env python3
"""
LinkedIn Article Scoring Criteria

Contains per-article-type scoring criteria definitions and CriteriaExtractor for
generating scoring-aware prompts. No LLM scoring is performed here — the criteria
are embedded into the generation prompt so the LLM optimizes for them directly.
"""

from typing import Dict, List, Optional
from models import FactCheckResult  # noqa: keep for fc_oc_v2 compatibility

# ==========================================================================
# VALID ARTICLE TYPES
# ==========================================================================

ARTICLE_TYPES = [
    "thought_leadership",
    "awareness",
    "demand_gen",
    "event_attendance",
    "recruitment",
    "product_announcement",
    "case_study",
]

ARTICLE_TYPE_LABELS: Dict[str, str] = {
    "thought_leadership": "Thought Leadership",
    "awareness": "Awareness",
    "demand_gen": "Demand Generation",
    "event_attendance": "Event Attendance",
    "recruitment": "Recruitment",
    "product_announcement": "Product Announcement",
    "case_study": "Case Study",
}

ARTICLE_TYPE_GOALS: Dict[str, str] = {
    "thought_leadership": (
        "Generate a deep, analytical thought leadership article that challenges conventional wisdom, "
        "applies first-principles thinking, and provides a unique strategic framework or perspective. "
        "The goal is to establish the author as an authoritative voice in their field."
    ),
    "awareness": (
        "Generate an awareness article that educates and builds brand recognition among people who "
        "may be unfamiliar with the topic or author. The goal is broad reach, shareability, and "
        "attracting new followers — not selling. Keep the tone warm, jargon-free, and inclusive."
    ),
    "demand_gen": (
        "Generate a demand generation article designed to drive qualified leads or conversions. "
        "Vividly articulate the problem and its cost, present a compelling solution with specific "
        "proof points, handle objections, and close with a clear, low-friction call to action."
    ),
    "event_attendance": (
        "Generate an article to drive registrations for a specific event (conference, webinar, "
        "workshop, etc.). Highlight the unique value and specific sessions/speakers, create genuine "
        "FOMO, speak directly to the ideal attendee, and make registering effortless."
    ),
    "recruitment": (
        "Generate a recruitment article to attract qualified candidates. Authentically portray "
        "the culture, values, and growth opportunities. Speak directly to what ambitious candidates "
        "care about and make applying feel like an exciting next step, not a transaction."
    ),
    "product_announcement": (
        "Generate a product or feature announcement article that creates genuine excitement without "
        "over-hyping. Explain the problem it solves, the tangible user benefits, early validation, "
        "and how to get access — maintaining credibility throughout."
    ),
    "case_study": (
        "Generate a case study article that builds credibility through a compelling customer success "
        "story. Make the challenge relatable, narrate the solution journey authentically, prove "
        "results with specific metrics, and extract transferable lessons for the reader."
    ),
}


# ==========================================================================
# SCORING CRITERIA — THOUGHT LEADERSHIP (original, 180 points)
# ==========================================================================

SCORING_CRITERIA_THOUGHT_LEADERSHIP = {
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
# SCORING CRITERIA — AWARENESS (145 points)
# ==========================================================================

SCORING_CRITERIA_AWARENESS = {
    "Hook & First Impression": [
        {
            "question": "Does the opening immediately grab attention from someone completely unfamiliar with the topic?",
            "points": 20,
            "scale": {
                1: "Assumes prior knowledge; cold readers bounce immediately",
                3: "Somewhat accessible but requires context to appreciate",
                5: "Immediately engaging and intriguing for any audience member",
            },
        },
        {
            "question": "Does the title or opening clearly signal the value to a cold audience without insider language?",
            "points": 15,
            "scale": {
                1: "Jargon-heavy or cryptic; only insiders understand the hook",
                3: "Somewhat clear but not compelling to strangers",
                5: "Crystal clear value signal that works for people who've never heard of this before",
            },
        },
    ],
    "Educational Clarity & Simplicity": [
        {
            "question": "Are complex ideas broken down into simple, digestible explanations without unnecessary jargon?",
            "points": 25,
            "scale": {
                1: "Dense technical language with no accommodation for newcomers",
                3: "Some explanations offered but inconsistently applied",
                5: "Expert ideas explained so clearly that anyone can understand and remember them",
            },
        },
        {
            "question": "Does the article build understanding progressively, leading readers from familiar concepts to new ones?",
            "points": 15,
            "scale": {
                1: "Jumps between unrelated concepts with no knowledge scaffolding",
                3: "Some logical progression but leaves gaps newcomers will struggle with",
                5: "Perfect knowledge scaffolding — each idea prepares the reader for the next",
            },
        },
    ],
    "Storytelling & Memorability": [
        {
            "question": "Are abstract concepts grounded in concrete, relatable stories, examples, or analogies?",
            "points": 15,
            "scale": {
                1: "Abstract concepts with no real-world grounding",
                3: "Some examples but not vivid or memorable",
                5: "Memorable stories and analogies that make every concept stick",
            },
        },
    ],
    "Shareability & Broad Appeal": [
        {
            "question": "Would readers want to share this article with people outside their immediate professional circle?",
            "points": 20,
            "scale": {
                1: "Too niche or insider to share widely",
                3: "Somewhat shareable within the industry",
                5: "Genuinely valuable to share across diverse networks",
            },
        },
        {
            "question": "Does the article avoid polarizing positions or insider debates that would limit its audience?",
            "points": 10,
            "scale": {
                1: "Takes controversial stances that alienate large segments",
                3: "Mostly neutral but with occasional alienating moments",
                5: "Inclusive framing that maximizes audience reach without sacrificing authenticity",
            },
        },
    ],
    "Brand Voice & Authenticity": [
        {
            "question": "Does the article feel genuinely human and warm rather than corporate, promotional, or AI-generated?",
            "points": 15,
            "scale": {
                1: "Reads like a press release or marketing brochure",
                3: "Some warmth but inconsistent — falls into corporate-speak at times",
                5: "Genuinely human voice throughout; feels like a real person sharing something they care about",
            },
        },
    ],
    "Call to Follow & Connect": [
        {
            "question": "Does it end with a soft, community-building invitation (follow, comment, share) rather than a sales pitch?",
            "points": 10,
            "scale": {
                1: "No CTA, hard sales push, or completely generic 'thoughts?'",
                3: "Friendly close but generic",
                5: "Warm, specific invitation that makes the right reader want to follow and engage",
            },
        },
    ],
    "Idea Density & Clarity": [
        {
            "question": "Is there one clear, central takeaway that readers will remember and repeat?",
            "points": 5,
            "scale": {
                1: "Multiple competing ideas that dilute the message",
                3: "Mostly one theme but some tangents",
                5: "One powerful, memorable idea that anchors everything else",
            },
        },
    ],
}


# ==========================================================================
# SCORING CRITERIA — DEMAND GENERATION (140 points)
# ==========================================================================

SCORING_CRITERIA_DEMAND_GEN = {
    "Problem Agitation": [
        {
            "question": "Does the article vividly articulate the pain, cost, or risk of NOT solving this problem?",
            "points": 20,
            "scale": {
                1: "Mentions the problem but fails to evoke any real urgency or discomfort",
                3: "Problem is clear but not viscerally felt by the reader",
                5: "Readers feel the problem acutely and recognize it in their own situation",
            },
        },
        {
            "question": "Are the consequences of inaction specific and quantified (time wasted, money lost, opportunities missed)?",
            "points": 15,
            "scale": {
                1: "Vague references to 'challenges' with no specificity",
                3: "Some specific consequences but not consistently quantified",
                5: "Concrete, quantified consequences that make inaction feel costly",
            },
        },
    ],
    "Value Proposition Clarity": [
        {
            "question": "Is the solution and its specific benefits explained in clear, outcome-focused language (not feature lists)?",
            "points": 25,
            "scale": {
                1: "Feature-focused without connecting to reader outcomes",
                3: "Benefits mentioned but vague or generic",
                5: "Clear before/after contrast with specific outcomes the reader can picture themselves achieving",
            },
        },
        {
            "question": "Does it differentiate from alternatives with specific, defensible, and credible claims?",
            "points": 15,
            "scale": {
                1: "Generic claims that any competitor could make",
                3: "Some differentiation but not compelling or defensible",
                5: "Sharp, credible differentiation backed by proof that establishes clear superiority",
            },
        },
    ],
    "Social Proof & Credibility": [
        {
            "question": "Are there specific data points, case studies, customer outcomes, or testimonials that prove the value?",
            "points": 20,
            "scale": {
                1: "No proof beyond assertions and opinions",
                3: "Some proof but generic or unspecific",
                5: "Specific, credible proof points that overcome skepticism and build trust",
            },
        },
    ],
    "Objection Handling": [
        {
            "question": "Does the article proactively surface and address the most common reasons someone would hesitate or say no?",
            "points": 15,
            "scale": {
                1: "Ignores objections entirely",
                3: "Addresses some objections but leaves the main ones open",
                5: "Systematically dismantles key objections with specific evidence and empathy",
            },
        },
    ],
    "Urgency & Specificity": [
        {
            "question": "Does the article create genuine, data-backed urgency without resorting to artificial hype or pressure?",
            "points": 10,
            "scale": {
                1: "No urgency, or manufactured scarcity that feels dishonest",
                3: "Some urgency but it feels generic or forced",
                5: "Authentic, evidence-backed reasons why acting now is better than waiting",
            },
        },
    ],
    "Call to Action": [
        {
            "question": "Is the CTA specific, low-friction, and calibrated to where the reader is in the buying journey?",
            "points": 20,
            "scale": {
                1: "No CTA, or a generic 'contact us' that feels like a big ask",
                3: "CTA exists but is too high-friction or unclear about what happens next",
                5: "Compelling, specific, low-friction CTA that matches reader readiness and makes the next step obvious",
            },
        },
    ],
    "Hook & Engagement": [
        {
            "question": "Does the opening immediately engage readers who experience the problem and promise a solution?",
            "points": 10,
            "scale": {
                1: "Bland opening that doesn't connect to reader pain",
                3: "Reasonably engaging but not targeted to the specific audience",
                5: "Opening that makes the ideal reader feel instantly seen and want to keep reading",
            },
        },
    ],
    "Idea Density & Clarity": [
        {
            "question": "Is the article concise and free of filler, keeping the reader moving toward the CTA?",
            "points": 5,
            "scale": {
                1: "Padded with tangents that reduce conversion momentum",
                3: "Mostly on-point with occasional diversions",
                5: "Every section advances the reader toward a clear decision",
            },
        },
    ],
}


# ==========================================================================
# SCORING CRITERIA — EVENT ATTENDANCE (155 points)
# ==========================================================================

SCORING_CRITERIA_EVENT_ATTENDANCE = {
    "Event Value Proposition": [
        {
            "question": "Is it immediately clear what unique value this event offers that cannot be obtained from a recording, blog post, or competing event?",
            "points": 25,
            "scale": {
                1: "Generic 'come learn and network' invitation with no unique differentiation",
                3: "Some unique value articulated but not compelling enough to act on",
                5: "Specific, unmissable value that is clearly stated and impossible to replicate elsewhere",
            },
        },
        {
            "question": "Are specific sessions, speakers, workshops, or experiences highlighted to create real anticipation?",
            "points": 20,
            "scale": {
                1: "No specifics — just vague promises of 'great content and speakers'",
                3: "Some highlights mentioned but not compelling or specific enough",
                5: "Specific highlights that create genuine excitement and a sense of 'I need to be in that room'",
            },
        },
    ],
    "FOMO & Exclusivity": [
        {
            "question": "Does the article create genuine FOMO through scarcity, exclusivity, or one-time access that feels authentic rather than manufactured?",
            "points": 15,
            "scale": {
                1: "No scarcity or FOMO — event feels available anytime",
                3: "FOMO attempted but feels artificial or exaggerated",
                5: "Authentic scarcity or exclusivity that naturally motivates the right reader to register now",
            },
        },
        {
            "question": "Does it clearly communicate what the ideal attendee will lose professionally or personally by not attending?",
            "points": 15,
            "scale": {
                1: "No cost-of-missing framing — staying home feels fine",
                3: "Vague reference to missing out without specific consequence",
                5: "Specific, credible consequences of absence that make the ideal attendee feel they cannot afford to miss this",
            },
        },
    ],
    "Target Audience Resonance": [
        {
            "question": "Does the article speak directly and specifically to the ideal attendee's current situation, goals, and challenges?",
            "points": 20,
            "scale": {
                1: "Generic audience targeting — could be for anyone",
                3: "Some persona specificity but still fairly broad",
                5: "So specific that the right person feels personally invited and the wrong person self-selects out",
            },
        },
    ],
    "Logistics & Clarity": [
        {
            "question": "Are all practical details (date, time, location or virtual format, cost, what's included) clear and easy to find?",
            "points": 10,
            "scale": {
                1: "Key logistical details buried, missing, or confusing",
                3: "Details present but scattered throughout the article",
                5: "All practical details clear, prominent, and structured so readers can act immediately",
            },
        },
    ],
    "Social Proof": [
        {
            "question": "Are there testimonials, past attendee stories, or success metrics from previous editions that reduce registration hesitation?",
            "points": 15,
            "scale": {
                1: "No proof of past success or attendee satisfaction",
                3: "Some social proof but generic ('great event!')",
                5: "Specific, compelling testimonials or metrics that make the event feel proven and worth attending",
            },
        },
    ],
    "Hook & Urgency": [
        {
            "question": "Does the opening immediately create urgency and curiosity specifically for the target attendee?",
            "points": 15,
            "scale": {
                1: "Bland, generic opening that doesn't create urgency",
                3: "Reasonably interesting but urgency is weak",
                5: "Opening that makes the ideal attendee feel immediate urgency and excitement to learn more",
            },
        },
    ],
    "Registration CTA": [
        {
            "question": "Is the registration call-to-action clear, compelling, and repeated at the right moments in the article?",
            "points": 20,
            "scale": {
                1: "No clear registration prompt or buried at the end only",
                3: "CTA exists but is generic or easy to overlook",
                5: "Clear, compelling, and well-placed registration prompt that makes signing up feel like the obvious next step",
            },
        },
    ],
    "Storytelling & Atmosphere": [
        {
            "question": "Does the article paint a vivid picture of the event experience that makes readers feel they are missing something tangible?",
            "points": 10,
            "scale": {
                1: "Dry description of an event agenda",
                3: "Some atmosphere conveyed but not immersive",
                5: "Vivid, experiential writing that puts the reader in the room and makes them want to be there",
            },
        },
    ],
    "Idea Density & Clarity": [
        {
            "question": "Is every section of the article advancing the reader toward registration with no wasted content?",
            "points": 5,
            "scale": {
                1: "Tangents and filler that dilute registration momentum",
                3: "Mostly on-point with minor diversions",
                5: "Every paragraph serves the goal of inspiring registration",
            },
        },
    ],
}


# ==========================================================================
# SCORING CRITERIA — RECRUITMENT (145 points)
# ==========================================================================

SCORING_CRITERIA_RECRUITMENT = {
    "Role & Opportunity Clarity": [
        {
            "question": "Is it clear what the role involves and why this specific opportunity is exciting and different from similar roles elsewhere?",
            "points": 15,
            "scale": {
                1: "Vague role description with generic responsibilities",
                3: "Role is clear but not positioned as exciting or differentiated",
                5: "Role and its unique opportunity are crystal clear and compelling to the right candidate",
            },
        },
        {
            "question": "Does the article explain what success looks like in this role and what the candidate will be building or achieving?",
            "points": 10,
            "scale": {
                1: "No vision of impact or success criteria",
                3: "Some mention of impact but vague",
                5: "Clear, exciting vision of what the candidate will accomplish and why it matters",
            },
        },
    ],
    "Culture & Values Authenticity": [
        {
            "question": "Does the culture portrayal feel genuine and specific rather than generic corporate values ('we value innovation and teamwork')?",
            "points": 20,
            "scale": {
                1: "Generic corporate culture-speak that any company could claim",
                3: "Some specificity but still feels polished and sanitized",
                5: "Authentic, specific culture details that only this company could say — rings true",
            },
        },
        {
            "question": "Does it give a genuine sense of the team, work environment, and day-to-day experience?",
            "points": 10,
            "scale": {
                1: "No insight into what working there actually feels like",
                3: "Some environment description but surface-level",
                5: "Vivid, honest picture of the team and environment that helps candidates self-select accurately",
            },
        },
    ],
    "Growth & Development": [
        {
            "question": "Does the article clearly articulate the learning, career growth, and development opportunities available in this role?",
            "points": 20,
            "scale": {
                1: "No mention of growth or learning opportunities",
                3: "Generic mentions of 'career development' without specifics",
                5: "Specific, compelling growth trajectory with concrete examples of how people advance",
            },
        },
    ],
    "Company Mission Alignment": [
        {
            "question": "Does the article connect the role to a larger mission or purpose that ambitious candidates find meaningful?",
            "points": 20,
            "scale": {
                1: "Role feels transactional with no connection to meaningful purpose",
                3: "Mission mentioned but feels distant from the day-to-day role",
                5: "Clear, credible connection between daily work and a mission that the ideal candidate finds genuinely meaningful",
            },
        },
    ],
    "Candidate Persona Resonance": [
        {
            "question": "Does the article speak directly to what the ideal candidate deeply cares about — not just job requirements but their aspirations and ambitions?",
            "points": 25,
            "scale": {
                1: "Reads like a job posting — requirements and benefits only",
                3: "Some candidate-centric framing but still mostly company-centric",
                5: "Speaks so directly to the ideal candidate's aspirations that they feel this was written for them",
            },
        },
    ],
    "Social Proof & Employee Voice": [
        {
            "question": "Are there specific employee stories, quotes, or experiences that make the culture feel real and trustworthy?",
            "points": 15,
            "scale": {
                1: "No employee voice or proof of the claimed culture",
                3: "Some proof but feels curated and overly positive",
                5: "Authentic employee stories that build real trust and credibility",
            },
        },
    ],
    "Application CTA": [
        {
            "question": "Does the article end with a clear, low-friction, and inviting call to apply or reach out?",
            "points": 10,
            "scale": {
                1: "No clear next step or a daunting application process described",
                3: "CTA present but generic",
                5: "Warm, specific invitation that makes applying feel exciting and accessible",
            },
        },
    ],
}


# ==========================================================================
# SCORING CRITERIA — PRODUCT ANNOUNCEMENT (145 points)
# ==========================================================================

SCORING_CRITERIA_PRODUCT_ANNOUNCEMENT = {
    "Novelty & Excitement Hook": [
        {
            "question": "Does the opening create genuine excitement about what is being announced without feeling like marketing hype?",
            "points": 20,
            "scale": {
                1: "Dry, corporate announcement with no excitement or human energy",
                3: "Some excitement but it feels forced or over-marketed",
                5: "Opening that creates authentic excitement and makes readers immediately want to know more",
            },
        },
    ],
    "Problem-Solution Fit": [
        {
            "question": "Is there a clear, specific problem stated before the solution — so readers understand exactly what this solves and for whom?",
            "points": 20,
            "scale": {
                1: "Jumps straight to features without establishing the problem",
                3: "Problem mentioned but not compellingly articulated",
                5: "The problem is so clearly articulated that readers recognize it before the solution is revealed",
            },
        },
        {
            "question": "Are specific, real-world use cases provided that show how users will apply this in practice?",
            "points": 10,
            "scale": {
                1: "No use cases — purely abstract capability descriptions",
                3: "Some use cases but generic or hypothetical",
                5: "Specific, vivid use cases that help readers immediately picture themselves using this",
            },
        },
    ],
    "Feature Clarity & Benefits": [
        {
            "question": "Are features explained in terms of user outcomes and benefits rather than technical specifications?",
            "points": 20,
            "scale": {
                1: "Feature list with no connection to user benefit",
                3: "Some benefit framing but often reverts to technical language",
                5: "Every feature is framed as a specific, tangible user outcome",
            },
        },
        {
            "question": "Is the impact quantified or grounded in specific before/after improvement?",
            "points": 10,
            "scale": {
                1: "Vague claims of improvement with no proof",
                3: "Some quantification but inconsistent",
                5: "Specific, credible quantification of the improvement users can expect",
            },
        },
    ],
    "Social Proof & Validation": [
        {
            "question": "Are there early user results, beta testimonials, or credible third-party validation that prove this works?",
            "points": 20,
            "scale": {
                1: "No proof beyond the company's own claims",
                3: "Some proof but thin or generic",
                5: "Compelling, specific early evidence that builds confidence in the announcement",
            },
        },
    ],
    "Competitive Differentiation": [
        {
            "question": "Does the article clearly explain why this is different from or better than existing alternatives in a credible, non-disparaging way?",
            "points": 20,
            "scale": {
                1: "No differentiation — readers wonder why they shouldn't stick with what they have",
                3: "Some differentiation claimed but not backed up",
                5: "Clear, credible differentiation that answers 'why switch?' without attacking competitors",
            },
        },
    ],
    "Access & Availability CTA": [
        {
            "question": "Is it clear how and when readers can get access, and is there a compelling reason to act now?",
            "points": 15,
            "scale": {
                1: "Vague about availability — readers don't know how to get it",
                3: "Availability mentioned but CTA is weak",
                5: "Clear, specific access path with a compelling reason to act immediately",
            },
        },
    ],
    "Tone Balance": [
        {
            "question": "Does the article strike the right balance between enthusiasm and credibility — excited without over-claiming?",
            "points": 10,
            "scale": {
                1: "Either too dry to be exciting or too hypey to be credible",
                3: "Reasonable balance but occasionally tips too far one way",
                5: "Perfect balance: genuinely exciting yet professionally credible throughout",
            },
        },
    ],
}


# ==========================================================================
# SCORING CRITERIA — CASE STUDY (145 points)
# ==========================================================================

SCORING_CRITERIA_CASE_STUDY = {
    "Challenge Relatability": [
        {
            "question": "Does the article open by articulating the challenge in a way that target readers immediately recognize as their own problem?",
            "points": 15,
            "scale": {
                1: "Challenge is described technically without evoking reader recognition",
                3: "Challenge is clear but not viscerally relatable",
                5: "Opening makes target readers think 'that's exactly the problem I'm dealing with'",
            },
        },
        {
            "question": "Is the business context and stakes of the challenge clearly established — so readers understand why it mattered?",
            "points": 10,
            "scale": {
                1: "No context for why the challenge was significant",
                3: "Some context but the stakes aren't fully conveyed",
                5: "Stakes are crystal clear — readers understand exactly what was at risk",
            },
        },
    ],
    "Solution Journey Narrative": [
        {
            "question": "Is the solution presented as a journey with clear steps, decisions, and real obstacles — not just a smooth success story?",
            "points": 15,
            "scale": {
                1: "Linear 'we did X and it worked' with no nuance or struggle",
                3: "Some journey detail but feels sanitized",
                5: "Authentic narrative with real decisions, pivots, and obstacles that makes the story credible and instructive",
            },
        },
        {
            "question": "Are the specific decisions, approaches, and implementation details clear enough to be instructive?",
            "points": 10,
            "scale": {
                1: "Too vague to learn anything actionable from",
                3: "Some specifics but still fairly high-level",
                5: "Specific enough that readers can extract concrete lessons and approaches",
            },
        },
    ],
    "Measurable Results & Proof": [
        {
            "question": "Are results quantified with specific metrics that clearly demonstrate impact (%, $, time saved, growth achieved)?",
            "points": 20,
            "scale": {
                1: "Vague claims of improvement with no numbers",
                3: "Some metrics provided but inconsistently or without context",
                5: "Specific, contextualized metrics that make the results undeniable and impressive",
            },
        },
        {
            "question": "Is there a clear before/after contrast that makes the improvement tangible?",
            "points": 10,
            "scale": {
                1: "No baseline established — results float without context",
                3: "Some before/after but not sharply contrasted",
                5: "Vivid before/after contrast that makes the transformation feel real and meaningful",
            },
        },
    ],
    "Customer Voice Authenticity": [
        {
            "question": "Does the customer's voice come through with specific quotes, real details, or personal perspective — rather than sanitized corporate-speak?",
            "points": 20,
            "scale": {
                1: "Generic, obviously PR-approved language with no authentic customer voice",
                3: "Some quotes or details but still feels polished and staged",
                5: "Authentic customer voice with specific, real details that make the story credible",
            },
        },
    ],
    "Transferable Lessons": [
        {
            "question": "Does the article extract lessons or principles from this specific case that readers can apply to their own situations?",
            "points": 15,
            "scale": {
                1: "Story told with no attempt to extract generalizable lessons",
                3: "Some lessons mentioned but not clearly connected to the story",
                5: "Specific, actionable lessons that readers can immediately apply — making the case study valuable beyond its specific context",
            },
        },
        {
            "question": "Are the lessons framed in a way that applies beyond the specific industry or company size of the case?",
            "points": 10,
            "scale": {
                1: "Lessons only apply to identical situations",
                3: "Some transferability but limited by specificity of context",
                5: "Principles that clearly generalize across industries, sizes, and situations",
            },
        },
    ],
    "Storytelling Arc": [
        {
            "question": "Is the case study structured as a compelling narrative (challenge → struggle → solution → results → lessons) rather than a flat report?",
            "points": 10,
            "scale": {
                1: "Reads like a bullet-point report with no narrative arc",
                3: "Some narrative elements but doesn't fully commit to storytelling",
                5: "Clear, engaging narrative arc that keeps readers engaged through to the lessons",
            },
        },
    ],
    "Soft Next Step CTA": [
        {
            "question": "Does the article end with a low-pressure invitation to learn more, discuss, or explore similar solutions?",
            "points": 10,
            "scale": {
                1: "No close, or an aggressive sales push that undercuts credibility",
                3: "Soft close but generic",
                5: "Natural, credible invitation that feels like a logical next step given what was just read",
            },
        },
    ],
}


# ==========================================================================
# ARTICLE TYPE → CRITERIA MAPPING
# ==========================================================================

ARTICLE_TYPE_CRITERIA = {
    "thought_leadership": SCORING_CRITERIA_THOUGHT_LEADERSHIP,
    "awareness": SCORING_CRITERIA_AWARENESS,
    "demand_gen": SCORING_CRITERIA_DEMAND_GEN,
    "event_attendance": SCORING_CRITERIA_EVENT_ATTENDANCE,
    "recruitment": SCORING_CRITERIA_RECRUITMENT,
    "product_announcement": SCORING_CRITERIA_PRODUCT_ANNOUNCEMENT,
    "case_study": SCORING_CRITERIA_CASE_STUDY,
}

# Keep backward-compatible alias
SCORING_CRITERIA = SCORING_CRITERIA_THOUGHT_LEADERSHIP


# ==========================================================================
# CRITERIA EXTRACTOR
# ==========================================================================


class CriteriaExtractor:
    """
    Extracts and formats scoring criteria for article generation prompts.
    The criteria are embedded in the generation prompt so the LLM optimizes
    for them directly — no separate scoring step needed.
    """

    def __init__(self, min_length: int, max_length: int, article_type: str = "thought_leadership"):
        if article_type not in ARTICLE_TYPE_CRITERIA:
            raise ValueError(
                f"Unknown article_type {article_type!r}. Valid types: {ARTICLE_TYPES}"
            )
        self.article_type = article_type
        self.criteria = ARTICLE_TYPE_CRITERIA[article_type]
        self.min_length = min_length
        self.max_length = max_length
        self._category_weights: Optional[Dict[str, int]] = None

    def get_article_type_description(self) -> str:
        """Return the goal description for the selected article type."""
        return ARTICLE_TYPE_GOALS[self.article_type]

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
        type_label = ARTICLE_TYPE_LABELS.get(self.article_type, self.article_type.replace("_", " ").title())
        lines = [
            f"SCORING CRITERIA FOR {type_label.upper()} ARTICLE GENERATION:",
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

        # Build optimization priorities based on top 3 weighted categories
        top_cats = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
        lines.extend([
            "OPTIMIZATION PRIORITIES:",
            "1. Article length is most important (200 points)",
        ])
        for i, (cat, pts) in enumerate(top_cats, 2):
            lines.append(f"{i}. Focus heavily on {cat} ({pts} points)")

        return "\n".join(lines)
