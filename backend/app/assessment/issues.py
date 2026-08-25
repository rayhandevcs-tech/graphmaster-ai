"""The unified issue: one shape for everything any analyzer finds.

Every analyzer — grammar, spelling, sentence quality, word usage, graph
accuracy — returns these. That is what lets the result page show one list
ordered by where the problems appear in the answer, rather than five lists the
student has to correlate by eye, and what lets "the most common mistakes in
this class" be one query rather than five.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.assessment import MAX_EXPLANATION_CHARS
from app.models.enums import IssueCategory, IssueSeverity


@dataclass(frozen=True, slots=True)
class AssessmentIssue:
    """One thing worth telling the student about one span of their answer.

    ``start`` and ``end`` are half-open indices into the **original submitted
    text**, so ``text[start:end]`` is exactly the span — the same contract the
    vocabulary highlights already honour. An analyzer working on normalised
    text must map its offsets back through
    :class:`~app.nlp.normalise.NormalisedText` before constructing one of
    these, or the highlight will land on the wrong words.
    """

    category: IssueCategory
    #: Stable slug, e.g. ``subject_verb_agreement``. This is the grouping key
    #: for "the mistakes this class makes most", so it must not be phrased for
    #: display — the human wording lives in ``explanation`` and can be
    #: rewritten without breaking a year of analytics.
    subtype: str
    severity: IssueSeverity
    original_text: str
    #: Why this is a problem, addressed to the student. Never a rule number.
    explanation: str
    start: int
    end: int
    #: ``None`` when there is no single right answer — "this sentence is hard
    #: to follow" has no replacement text, and inventing one would be worse
    #: than offering none.
    suggested_text: str | None = None
    #: 0–1. Issues below the deployment's floor are recorded but not shown, so
    #: a false-positive rate can be tuned from evidence instead of guessed.
    confidence: float = 1.0
    #: Which analyzer, and which provider within it, produced this. Needed to
    #: audit a false positive back to its cause.
    source: str = "unknown"

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(
                f"Issue span [{self.start}, {self.end}) is not a valid half-open range."
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Issue confidence {self.confidence} is outside 0–1.")
        if not self.subtype:
            raise ValueError("An issue must carry a subtype; it is the analytics key.")

    @property
    def fingerprint(self) -> str:
        """Identity for deduplication.

        Two analyzers can legitimately reach the same conclusion about the
        same span — a spell checker and a grammar checker both objecting to
        the same word, say. Showing it twice reads as the system stuttering,
        so the supervisor keeps the more confident one.
        """
        material = f"{self.category}|{self.subtype}|{self.start}|{self.end}"
        return hashlib.blake2s(material.encode("utf-8"), digest_size=8).hexdigest()

    def truncated(self) -> AssessmentIssue:
        """A copy whose explanation fits the column it will be stored in."""
        if len(self.explanation) <= MAX_EXPLANATION_CHARS:
            return self
        # Cut on a word boundary: a sentence severed mid-word reads as
        # corruption rather than as an abbreviation.
        cut = self.explanation[: MAX_EXPLANATION_CHARS - 1].rsplit(" ", 1)[0]
        return AssessmentIssue(
            category=self.category,
            subtype=self.subtype,
            severity=self.severity,
            original_text=self.original_text,
            explanation=f"{cut}…",
            start=self.start,
            end=self.end,
            suggested_text=self.suggested_text,
            confidence=self.confidence,
            source=self.source,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "subtype": self.subtype,
            "severity": self.severity.value,
            "original_text": self.original_text,
            "suggested_text": self.suggested_text,
            "explanation": self.explanation,
            "start": self.start,
            "end": self.end,
            "confidence": round(self.confidence, 4),
            "source": self.source,
        }


def order_for_display(issues: list[AssessmentIssue]) -> list[AssessmentIssue]:
    """Reading order, then severity.

    A student works through their answer from the top; a list grouped by
    analyzer would make them jump around their own writing. Ties break on
    severity so that where two issues share a span, the one asserting an error
    is read before the one offering a preference.
    """
    rank = {IssueSeverity.ERROR: 0, IssueSeverity.WARNING: 1, IssueSeverity.SUGGESTION: 2}
    return sorted(issues, key=lambda i: (i.start, rank[i.severity], i.category.value, i.subtype))


def deduplicate(issues: list[AssessmentIssue]) -> list[AssessmentIssue]:
    """Drop repeats of the same finding, keeping the most confident."""
    best: dict[str, AssessmentIssue] = {}
    for issue in issues:
        existing = best.get(issue.fingerprint)
        if existing is None or issue.confidence > existing.confidence:
            best[issue.fingerprint] = issue
    return list(best.values())


__all__ = ["AssessmentIssue", "deduplicate", "order_for_display"]
