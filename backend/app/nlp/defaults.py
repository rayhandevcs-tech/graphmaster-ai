"""Type-derived default target vocabulary (FR-5.6).

A graph cannot be *published* without at least one required target term, so in
normal operation every scored submission has a curated set. This is the
fallback for the case Sprint 3's rule does not cover — an unpublished draft a
teacher is previewing — and the starting point offered when they open the
target editor on a new graph.

The categories differ by chart type because the language does. A pie chart has
no time axis, so asking for fluctuation vocabulary would mark a student down
for not describing movement that is not there.
"""

from __future__ import annotations

from app.models.enums import GraphType

#: Vocabulary categories relevant to each chart type, most important first.
DEFAULT_CATEGORIES: dict[GraphType, tuple[str, ...]] = {
    GraphType.LINE: ("increase", "decrease", "fluctuation", "peak", "lowest", "stability"),
    GraphType.BAR: ("comparison", "peak", "lowest", "increase", "decrease"),
    # No movement language: a pie chart is a single snapshot of proportions.
    GraphType.PIE: ("comparison", "peak", "lowest"),
    GraphType.AREA: ("increase", "decrease", "stability", "comparison", "peak"),
}

#: Terms taken from each category before moving on to the next.
TERMS_PER_CATEGORY = 2

#: Ceiling on a generated set.
#:
#: PROJECT_PLAN §3.2 settles on 8–12 curated terms per graph; a denominator far
#: above that puts the crown tier out of reach in a 150-word answer.
MAX_DEFAULT_TARGETS = 10


def default_categories(graph_type: GraphType) -> tuple[str, ...]:
    """Category codes to draw a default target set from, in priority order."""
    return DEFAULT_CATEGORIES.get(graph_type, DEFAULT_CATEGORIES[GraphType.LINE])
