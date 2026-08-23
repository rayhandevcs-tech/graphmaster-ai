"""Seed data definitions.

Kept as plain data structures, separate from the insertion logic, so the
content is reviewable by a teacher without reading any code.
"""

from __future__ import annotations

from typing import Any

# ── Avatars ──────────────────────────────────────────────────────────────────
# Art is referenced by path; the files ship under frontend/public/avatars/.

AVATARS: list[dict[str, Any]] = [
    {
        "code": "boy_default",
        "name": "Arif",
        "gender": "male",
        "image_url": "/avatars/boy-default.svg",
        "is_default": True,
        "unlock_level": 1,
    },
    {
        "code": "girl_default",
        "name": "Nadia",
        "gender": "female",
        "image_url": "/avatars/girl-default.svg",
        "is_default": True,
        "unlock_level": 1,
    },
    {
        "code": "boy_scholar",
        "name": "Arif the Scholar",
        "gender": "male",
        "image_url": "/avatars/boy-scholar.svg",
        "is_default": False,
        "unlock_level": 10,
    },
    {
        "code": "girl_scholar",
        "name": "Nadia the Scholar",
        "gender": "female",
        "image_url": "/avatars/girl-scholar.svg",
        "is_default": False,
        "unlock_level": 10,
    },
    {
        "code": "boy_explorer",
        "name": "Arif the Explorer",
        "gender": "male",
        "image_url": "/avatars/boy-explorer.svg",
        "is_default": False,
        "unlock_level": 25,
    },
    {
        "code": "girl_explorer",
        "name": "Nadia the Explorer",
        "gender": "female",
        "image_url": "/avatars/girl-explorer.svg",
        "is_default": False,
        "unlock_level": 25,
    },
]


# ── Vocabulary ───────────────────────────────────────────────────────────────

VOCABULARY_CATEGORIES: list[dict[str, Any]] = [
    {
        "code": "increase",
        "name": "Increase",
        "description": "Language describing upward movement or growth.",
        "display_order": 1,
    },
    {
        "code": "decrease",
        "name": "Decrease",
        "description": "Language describing downward movement or reduction.",
        "display_order": 2,
    },
    {
        "code": "fluctuation",
        "name": "Fluctuation",
        "description": "Language describing irregular or unstable movement.",
        "display_order": 3,
    },
    {
        "code": "stability",
        "name": "Stability",
        "description": "Language describing values that stay level.",
        "display_order": 4,
    },
    {
        "code": "comparison",
        "name": "Comparison",
        "description": "Language contrasting two or more values or series.",
        "display_order": 5,
    },
    {
        "code": "peak",
        "name": "Peak",
        "description": "Language identifying maximum values.",
        "display_order": 6,
    },
    {
        "code": "lowest",
        "name": "Lowest",
        "description": "Language identifying minimum values.",
        "display_order": 7,
    },
]

# `lemma` is the normalised key the analyser matches against. For single words
# it is the spaCy lemma; for phrases it is the space-joined lemma sequence, so
# "bottomed out" matches the stored "bottom out".
VOCABULARY_ITEMS: list[dict[str, Any]] = [
    # Increase
    {"category": "increase", "term": "increase", "lemma": "increase", "weight": 1.00},
    {"category": "increase", "term": "rise", "lemma": "rise", "weight": 1.00},
    {"category": "increase", "term": "grow", "lemma": "grow", "weight": 1.00},
    {"category": "increase", "term": "surge", "lemma": "surge", "weight": 1.25},
    {"category": "increase", "term": "climb", "lemma": "climb", "weight": 1.25},
    {"category": "increase", "term": "soar", "lemma": "soar", "weight": 1.50},
    # Decrease
    {"category": "decrease", "term": "decrease", "lemma": "decrease", "weight": 1.00},
    {"category": "decrease", "term": "decline", "lemma": "decline", "weight": 1.00},
    {"category": "decrease", "term": "drop", "lemma": "drop", "weight": 1.00},
    {"category": "decrease", "term": "fall", "lemma": "fall", "weight": 1.00},
    {"category": "decrease", "term": "reduce", "lemma": "reduce", "weight": 1.00},
    {"category": "decrease", "term": "plummet", "lemma": "plummet", "weight": 1.50},
    # Fluctuation
    {"category": "fluctuation", "term": "fluctuate", "lemma": "fluctuate", "weight": 1.50},
    {"category": "fluctuation", "term": "vary", "lemma": "vary", "weight": 1.00},
    {"category": "fluctuation", "term": "oscillate", "lemma": "oscillate", "weight": 1.50},
    # Stability
    {"category": "stability", "term": "stable", "lemma": "stable", "weight": 1.00},
    {"category": "stability", "term": "constant", "lemma": "constant", "weight": 1.00},
    {"category": "stability", "term": "steady", "lemma": "steady", "weight": 1.00},
    {"category": "stability", "term": "plateau", "lemma": "plateau", "weight": 1.50},
    # Comparison — phrases
    {
        "category": "comparison",
        "term": "higher than",
        "lemma": "high than",
        "weight": 1.00,
        "is_phrase": True,
    },
    {
        "category": "comparison",
        "term": "lower than",
        "lemma": "low than",
        "weight": 1.00,
        "is_phrase": True,
    },
    {
        "category": "comparison",
        "term": "compared with",
        "lemma": "compare with",
        "weight": 1.25,
        "is_phrase": True,
    },
    {
        "category": "comparison",
        "term": "in contrast to",
        "lemma": "in contrast to",
        "weight": 1.50,
        "is_phrase": True,
    },
    # Peak
    {"category": "peak", "term": "peak", "lemma": "peak", "weight": 1.00},
    {
        "category": "peak",
        "term": "highest point",
        "lemma": "high point",
        "weight": 1.00,
        "is_phrase": True,
    },
    {
        "category": "peak",
        "term": "reach a maximum",
        "lemma": "reach a maximum",
        "weight": 1.50,
        "is_phrase": True,
    },
    # Lowest
    {
        "category": "lowest",
        "term": "lowest point",
        "lemma": "low point",
        "weight": 1.00,
        "is_phrase": True,
    },
    {
        "category": "lowest",
        "term": "bottom out",
        "lemma": "bottom out",
        "weight": 1.50,
        "is_phrase": True,
    },
    {"category": "lowest", "term": "trough", "lemma": "trough", "weight": 1.50},
]


# ── Badges ───────────────────────────────────────────────────────────────────

BADGES: list[dict[str, Any]] = [
    {
        "code": "royal_vocabulary_master",
        "name": "Royal Vocabulary Master",
        "description": "Used 90% or more of the target vocabulary for a graph.",
        "icon": "👑",
        "reward_tier": "crown",
    },
    {
        "code": "rising_writer",
        "name": "Rising Writer",
        "description": "Used 60–89% of the target vocabulary for a graph.",
        "icon": "🌸",
        "reward_tier": "flower",
    },
    {
        "code": "steady_learner",
        "name": "Steady Learner",
        "description": "Used 50–59% of the target vocabulary. Nearly there.",
        "icon": "🌱",
        "reward_tier": "steady",
    },
    {
        "code": "practice_needed",
        "name": "Practice Needed",
        "description": "Used under 50% of the target vocabulary. Keep practising!",
        "icon": "🔨",
        "reward_tier": "hammer",
    },
]


# ── Achievements ─────────────────────────────────────────────────────────────
# `rule` is evaluated by GamificationService, so a new achievement is a data
# change rather than a code change.

ACHIEVEMENTS: list[dict[str, Any]] = [
    {
        "code": "first_submission",
        "title": "First Steps",
        "description": "Complete your first graph description.",
        "icon": "🎯",
        "xp_reward": 50,
        "rule": {"type": "submission_count", "threshold": 1},
        "display_order": 1,
    },
    {
        "code": "ten_submissions",
        "title": "Getting Serious",
        "description": "Complete 10 graph descriptions.",
        "icon": "📈",
        "xp_reward": 100,
        "rule": {"type": "submission_count", "threshold": 10},
        "display_order": 2,
    },
    {
        "code": "fifty_submissions",
        "title": "Dedicated Learner",
        "description": "Complete 50 graph descriptions.",
        "icon": "📚",
        "xp_reward": 300,
        "rule": {"type": "submission_count", "threshold": 50},
        "display_order": 3,
    },
    {
        "code": "hundred_submissions",
        "title": "Centurion",
        "description": "Complete 100 graph descriptions.",
        "icon": "💯",
        "xp_reward": 500,
        "rule": {"type": "submission_count", "threshold": 100},
        "display_order": 4,
    },
    {
        "code": "graph_king",
        "title": "Graph King",
        "description": "Reach the crown tier on a graph description.",
        "icon": "👑",
        "xp_reward": 200,
        "rule": {"type": "reward_tier_count", "tier": "crown", "threshold": 1, "gender": "male"},
        "display_order": 5,
    },
    {
        "code": "graph_queen",
        "title": "Graph Queen",
        "description": "Reach the crown tier on a graph description.",
        "icon": "👑",
        "xp_reward": 200,
        "rule": {"type": "reward_tier_count", "tier": "crown", "threshold": 1, "gender": "female"},
        "display_order": 6,
    },
    {
        "code": "vocabulary_master",
        "title": "Vocabulary Master",
        "description": "Score 90% or higher on vocabulary usage three times in a row.",
        "icon": "🧠",
        "xp_reward": 400,
        "rule": {
            "type": "vocabulary_percentage_threshold",
            "threshold": 90,
            "consecutive": 3,
        },
        "display_order": 7,
    },
    {
        "code": "consistency_champion",
        "title": "Consistency Champion",
        "description": "Practise on seven consecutive days.",
        "icon": "🔥",
        "xp_reward": 250,
        "rule": {"type": "streak_days", "threshold": 7},
        "display_order": 8,
    },
    {
        "code": "perfect_score",
        "title": "Perfect Score",
        "description": "Achieve a final score of 100.",
        "icon": "⭐",
        "xp_reward": 500,
        "rule": {"type": "final_score_threshold", "threshold": 100},
        "display_order": 9,
    },
    {
        "code": "well_rounded",
        "title": "Well Rounded",
        "description": "Describe all four graph types.",
        "icon": "🎨",
        "xp_reward": 150,
        "rule": {"type": "distinct_graph_types", "threshold": 4},
        "display_order": 10,
    },
]
