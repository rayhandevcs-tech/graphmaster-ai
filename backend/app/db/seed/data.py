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


# ── Sample practice graphs ───────────────────────────────────────────────────
# Four exercises, one per supported chart type, so a fresh install has
# something to practise on immediately. `chart_data` is the Chart.js payload
# the frontend renders directly; `targets` lists the *lemmas* of the terms a
# good description is expected to use — resolved to IDs at seed time so the
# list stays readable, and so a term renamed in the library keeps working.

SAMPLE_GRAPHS: list[dict[str, Any]] = [
    {
        "title": "Solar energy output, 2019–2025",
        "graph_type": "line",
        "difficulty": "beginner",
        "prompt": (
            "The line graph shows the solar energy generated by a university campus "
            "between 2019 and 2025. Summarise the information by selecting and "
            "reporting the main features, and make comparisons where relevant. "
            "Write at least 150 words."
        ),
        "chart_data": {
            "labels": ["2019", "2020", "2021", "2022", "2023", "2024", "2025"],
            "datasets": [
                {
                    "label": "Solar output (MWh)",
                    "data": [120, 145, 190, 260, 255, 340, 410],
                    "borderColor": "#7c3aed",
                    "backgroundColor": "rgba(124, 58, 237, 0.15)",
                }
            ],
            "x_axis_label": "Year",
            "y_axis_label": "Energy generated (MWh)",
            "unit": "MWh",
        },
        "reference_description": (
            "The line graph illustrates the amount of solar energy generated by a "
            "university campus over a seven-year period from 2019 to 2025. Overall, "
            "output rose substantially across the period, climbing from 120 MWh to "
            "410 MWh, although the upward trend was briefly interrupted in 2023. "
            "Generation increased steadily in the first three years, growing from "
            "120 MWh in 2019 to 190 MWh in 2021. The sharpest rise came in 2022, "
            "when output surged to 260 MWh. Figures then dipped slightly to their "
            "only decline of the period, falling to 255 MWh in 2023, before "
            "recovering. The highest point was reached in 2025 at 410 MWh, more "
            "than three times the 2019 figure and considerably higher than every "
            "preceding year."
        ),
        "targets": ["increase", "rise", "climb", "surge", "fall", "high point"],
    },
    {
        "title": "Library visits by faculty",
        "graph_type": "bar",
        "difficulty": "beginner",
        "prompt": (
            "The bar chart compares the average number of weekly library visits per "
            "student across four faculties in two academic years. Summarise the "
            "information and make comparisons where relevant. Write at least 150 words."
        ),
        "chart_data": {
            "labels": ["Engineering", "Business", "Humanities", "Medicine"],
            "datasets": [
                {
                    "label": "2023–24",
                    "data": [3.2, 2.1, 5.4, 4.8],
                    "backgroundColor": "#7c3aed",
                },
                {
                    "label": "2024–25",
                    "data": [3.9, 1.8, 5.1, 6.2],
                    "backgroundColor": "#2563eb",
                },
            ],
            "x_axis_label": "Faculty",
            "y_axis_label": "Average weekly visits per student",
        },
        "reference_description": (
            "The bar chart compares average weekly library visits per student across "
            "four faculties in two consecutive academic years. Overall, Medicine "
            "students visited most often by 2024–25, while Business students used the "
            "library least in both years. Humanities recorded the highest figure in "
            "2023–24 at 5.4 visits per week, which was considerably higher than "
            "Business at 2.1. In the following year Medicine rose sharply to 6.2 "
            "visits, overtaking Humanities, whose figure declined slightly to 5.1. "
            "Engineering grew from 3.2 to 3.9 visits, remaining relatively stable "
            "compared with the other faculties. Business was the only faculty to drop "
            "in both absolute and relative terms, falling to 1.8 visits and reaching "
            "the lowest point on the chart."
        ),
        "targets": ["high than", "low than", "compare with", "rise", "decline", "stable"],
    },
    {
        "title": "How students travel to campus",
        "graph_type": "pie",
        "difficulty": "beginner",
        "prompt": (
            "The pie chart shows the proportion of students using each mode of "
            "transport to reach campus. Summarise the information by selecting and "
            "reporting the main features. Write at least 150 words."
        ),
        "chart_data": {
            "labels": ["Bus", "Walking", "Bicycle", "Car", "Train"],
            "datasets": [
                {
                    "label": "Share of students (%)",
                    "data": [38, 24, 17, 13, 8],
                    "backgroundColor": [
                        "#7c3aed",
                        "#2563eb",
                        "#f59e0b",
                        "#10b981",
                        "#ef4444",
                    ],
                }
            ],
            "y_axis_label": "Share of students (%)",
            "unit": "%",
        },
        "reference_description": (
            "The pie chart illustrates the proportion of students using five different "
            "modes of transport to travel to campus. Overall, public and active "
            "transport dominate, with the bus accounting for the largest single share "
            "and the train the smallest. The bus is by far the most common choice at "
            "38% of students, considerably higher than any other mode. Walking follows "
            "at 24%, while cycling accounts for 17%. Taken together, these three "
            "options represent almost four-fifths of all journeys. Car travel is "
            "comparatively low at 13%, lower than every active or public option except "
            "the train. The train represents the lowest point on the chart at just 8%, "
            "less than a quarter of the bus figure."
        ),
        "targets": ["high than", "low than", "compare with", "low point"],
    },
    {
        "title": "Campus water consumption by quarter",
        "graph_type": "area",
        "difficulty": "intermediate",
        "prompt": (
            "The area chart shows quarterly water consumption in two campus buildings "
            "over three years. Summarise the information by selecting and reporting "
            "the main features, and make comparisons where relevant. Write at least "
            "150 words."
        ),
        "chart_data": {
            "labels": [
                "Q1 2023",
                "Q2 2023",
                "Q3 2023",
                "Q4 2023",
                "Q1 2024",
                "Q2 2024",
                "Q3 2024",
                "Q4 2024",
                "Q1 2025",
                "Q2 2025",
                "Q3 2025",
                "Q4 2025",
            ],
            "datasets": [
                {
                    "label": "Science block (m³)",
                    "data": [820, 910, 640, 880, 860, 930, 610, 900, 840, 870, 590, 850],
                    "borderColor": "#7c3aed",
                    "backgroundColor": "rgba(124, 58, 237, 0.35)",
                    "fill": True,
                },
                {
                    "label": "Halls of residence (m³)",
                    "data": [1180, 1120, 430, 1210, 1150, 1090, 400, 1160, 1100, 1050, 380, 1090],
                    "borderColor": "#2563eb",
                    "backgroundColor": "rgba(37, 99, 235, 0.35)",
                    "fill": True,
                },
            ],
            "x_axis_label": "Quarter",
            "y_axis_label": "Water consumed (cubic metres)",
            "unit": "m³",
        },
        "reference_description": (
            "The area chart compares quarterly water consumption in two campus "
            "buildings over a three-year period. Overall, both buildings fluctuated "
            "seasonally rather than following any long-term trend, and the halls of "
            "residence consumed considerably more water than the science block in "
            "every quarter except the third of each year. Consumption in the halls "
            "oscillated dramatically, peaking at 1,210 m³ in Q4 2023 and bottoming out "
            "at around 400 m³ each third quarter, when the vacation empties the "
            "buildings. The science block varied far less, remaining relatively stable "
            "between roughly 590 and 930 m³ throughout. Its lowest point of 590 m³ came "
            "in Q3 2025, part of a slight downward drift in third-quarter figures. "
            "Both buildings showed a marginal decline across the three years, though "
            "the seasonal pattern remained constant."
        ),
        "targets": [
            "fluctuate",
            "oscillate",
            "vary",
            "peak",
            "bottom out",
            "stable",
            "constant",
            "decline",
            "high than",
        ],
    },
]
