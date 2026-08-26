"""Score assembly, reward tiers and engine versioning (FR-6.6 to FR-6.8, FR-7.1)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.models.enums import RewardTier
from app.nlp import ENGINE_VERSION
from app.nlp.detector import DetectionResult
from app.nlp.terms import CompiledTargets
from app.nlp.writing import WritingQuality


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """The numbers persisted on a ``Score`` row."""

    vocabulary_percentage: float
    vocabulary_score: float
    writing_score: float
    final_score: float
    reward_tier: RewardTier
    detected_count: int
    unique_detected_count: int
    total_target_count: int
    bonus_terms_used: int


def vocabulary_percentage(detection: DetectionResult, targets: CompiledTargets) -> float:
    """``(unique target terms detected ÷ required target terms) × 100`` (FR-6.6).

    The numerator counts **unique** terms, not occurrences. Counting
    occurrences would reward writing "increase" eight times over using eight
    different terms — the exact opposite of the vocabulary range the platform
    exists to teach.

    Optional targets are credited in the numerator but excluded from the
    denominator, so a teacher can offer bonus vocabulary without making the
    crown tier harder to reach. That is also why the result is capped: enough
    bonus terms could otherwise carry a student past 100%.
    """
    required = len(targets.required)
    if required == 0:
        # Nothing to measure against. Callers resolve a default target set
        # before reaching here (FR-5.6); this is the last line of defence
        # against a division by zero in the middle of scoring a submission.
        return 0.0

    detected_unique = len(detection.detected)
    return round(min(detected_unique / required * 100.0, 100.0), 2)


def reward_tier(percentage: float, settings: Settings) -> RewardTier:
    """The tier for a vocabulary percentage (FR-7.1).

    Driven by the **vocabulary percentage, not the final score** — the
    specification states the thresholds in those terms, and a student who used
    nine of ten target words has earned the crown even if their sentences were
    short.
    """
    if percentage >= settings.TIER_CROWN_MIN:
        return RewardTier.CROWN
    if percentage >= settings.TIER_FLOWER_MIN:
        return RewardTier.FLOWER
    if percentage >= settings.TIER_STEADY_MIN:
        return RewardTier.STEADY
    return RewardTier.HAMMER


def build_score(
    detection: DetectionResult,
    writing: WritingQuality,
    targets: CompiledTargets,
    settings: Settings,
) -> ScoreBreakdown:
    """Assemble the final score from its two weighted parts (FR-6.8)."""
    percentage = vocabulary_percentage(detection, targets)
    vocabulary = percentage  # already capped at 100
    writing_score = writing.score

    final = round(
        settings.VOCABULARY_WEIGHT * vocabulary + settings.WRITING_WEIGHT * writing_score, 2
    )

    return ScoreBreakdown(
        vocabulary_percentage=percentage,
        vocabulary_score=vocabulary,
        writing_score=writing_score,
        final_score=final,
        reward_tier=reward_tier(percentage, settings),
        detected_count=detection.total_occurrences,
        unique_detected_count=detection.unique_terms,
        # The **required** count, not every target: this is the denominator the
        # stored percentage was computed against, so a reader can reproduce the
        # percentage from the row without knowing the graph's current target
        # list — which a teacher may have changed since.
        total_target_count=len(targets.required),
        bonus_terms_used=sum(1 for d in detection.detected if not d.term.is_required),
    )


def category_breakdown(
    detection: DetectionResult, targets: CompiledTargets
) -> dict[str, dict[str, Any]]:
    """Per-category vocabulary usage (FR-6.11).

    Ordered by category code so the stored JSON is stable between runs and a
    diff of two scores shows real changes rather than dictionary ordering.
    """
    used: dict[str, list[str]] = {}
    for entry in detection.detected:
        used.setdefault(entry.term.category_code, []).append(entry.term.term)

    missing: dict[str, list[str]] = {}
    for term in detection.missing:
        missing.setdefault(term.category_code, []).append(term.term)

    names = {t.category_code: t.category_name for t in targets.terms}
    required_totals: dict[str, int] = {}
    for term in targets.required:
        required_totals[term.category_code] = required_totals.get(term.category_code, 0) + 1

    breakdown: dict[str, dict[str, Any]] = {}
    for code in sorted(names):
        detected_terms = sorted(used.get(code, []))
        total = required_totals.get(code, 0)
        breakdown[code] = {
            "name": names[code],
            "detected": detected_terms,
            "missing": sorted(missing.get(code, [])),
            "detected_count": len(detected_terms),
            "target_count": total,
            "percentage": (
                round(min(len(detected_terms) / total * 100.0, 100.0), 2) if total else 0.0
            ),
        }
    return breakdown


def rubric(settings: Settings) -> dict[str, Any]:
    """The deployed scoring configuration, as the API reports it."""
    return {
        "vocabulary_weight": settings.VOCABULARY_WEIGHT,
        "writing_weight": settings.WRITING_WEIGHT,
        "tier_thresholds": {
            RewardTier.CROWN.value: settings.TIER_CROWN_MIN,
            RewardTier.FLOWER.value: settings.TIER_FLOWER_MIN,
            RewardTier.STEADY.value: settings.TIER_STEADY_MIN,
            RewardTier.HAMMER.value: 0.0,
        },
        "target_word_count": {
            "min": settings.TARGET_WORD_COUNT_MIN,
            "max": settings.TARGET_WORD_COUNT_MAX,
        },
    }


def student_rubric(settings: Settings) -> dict[str, Any]:
    """The part of the rubric a student may be told (FR-6.1, FR-6.12).

    Deliberately a *separate* function rather than a filtered copy of
    :func:`rubric`. A filter is a list of keys to remove, and the failure mode
    of a removal list is that a key added later is published by default; this
    is a list of keys to include, whose failure mode is that a new one is
    withheld until someone decides otherwise.

    What is withheld, and why:

    * **Tier thresholds.** The tier is the reward, and a student who knows the
      crown starts at 90% is writing to a number rather than describing a
      chart. They are shown the tier they earned and what produced it, after
      the work.
    * **The language-model state and the engine version.** Deployment facts. A
      student can do nothing with either, and both name internals.

    What is published, and why:

    * **The weights**, because the marking criteria are not a secret — the
      opposite: FR-6.12 wants a student to understand that vocabulary carries
      most of the mark, and the alternative is a UI that hardcodes "70/30" and
      goes on saying it after the rubric is retuned.
    * **The word-count band.** The minimum is the task's own instruction. The
      maximum comes with it because the writing score penalises an over-long
      answer as well as a short one, and a floor published without its ceiling
      invites exactly the padding that loses marks. The feedback a student is
      already sent names the whole band in the same breath ("expects
      150-250"), so the ceiling is not new information — it is only earlier.

    Target vocabulary is not here and cannot be: this function never sees a
    graph.
    """
    return {
        "vocabulary_weight": settings.VOCABULARY_WEIGHT,
        "writing_weight": settings.WRITING_WEIGHT,
        "target_word_count": {
            "min": settings.TARGET_WORD_COUNT_MIN,
            "max": settings.TARGET_WORD_COUNT_MAX,
        },
    }


def engine_version(settings: Settings) -> str:
    """The version stamped on every score.

    The code version alone is not enough. Weights and tier thresholds are
    deployment configuration precisely so a study can retune the rubric without
    a redeploy (08-nlp-architecture.md §5.3) — which means two scores can carry
    the same engine version and yet be incomparable, silently invalidating
    exactly the cohort comparison the version field exists to protect.

    Appending a fingerprint of the deployed rubric closes that hole: a changed
    weight produces a visibly different version string.
    """
    material = "|".join(
        (
            f"{settings.VOCABULARY_WEIGHT:.4f}",
            f"{settings.WRITING_WEIGHT:.4f}",
            f"{settings.TIER_CROWN_MIN:.2f}",
            f"{settings.TIER_FLOWER_MIN:.2f}",
            f"{settings.TIER_STEADY_MIN:.2f}",
            str(settings.TARGET_WORD_COUNT_MIN),
            str(settings.TARGET_WORD_COUNT_MAX),
        )
    )
    digest = hashlib.blake2s(material.encode("utf-8"), digest_size=4).hexdigest()
    return f"{ENGINE_VERSION}+{digest}"
