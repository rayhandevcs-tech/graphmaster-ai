"""Spelling (Feature 2).

The hard part of spell-checking a graph description is not finding
misspellings. It is *not* finding them in the words that only look wrong: the
curated vocabulary the student is being marked on, the labels off the chart
they were asked to describe, and the proper nouns those labels are full of.
A checker that flags "Hokkaido" or "plateaued" teaches the student to ignore
it, and an ignored correction is worse than none.

So the exemption set is built first, from what this submission is actually
about, and only what survives it is looked up.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from app.assessment.issues import AssessmentIssue
from app.assessment.protocol import AnalyzerOutput, AssessmentContext
from app.assessment.text import chart_words, real_words, scale, token_span, words_in
from app.core.config import Settings
from app.core.logging import get_logger
from app.models.enums import AnalyzerStatus, IssueCategory, IssueSeverity

if TYPE_CHECKING:  # pragma: no cover
    from spacy.tokens import Token

logger = get_logger(__name__)

#: Below this length a "misspelling" is usually an abbreviation, an axis label
#: or a unit — "GDP", "km", "yr". Correcting those is noise.
MIN_LENGTH = 4

#: Accuracy at or above this earns full marks. Not 100%: one typo in a
#: 200-word answer is not the same failure as a page of them, and a scale that
#: only rewards perfection tells a student nothing about the distance between.
ACCURACY_CEILING = 99.0

#: Accuracy mapped to zero.
#:
#: Fifteen per cent of a description misspelled is a submission with a
#: different problem. The band is wide on purpose: a narrow one turns two
#: typos in a short answer into a failing spelling score, which says more
#: about the answer's length than about its spelling.
ACCURACY_FLOOR = 85.0

#: Suggestion within one edit of the word — a confident correction.
CONFIDENT_EDIT_DISTANCE = 1

#: Confidence for a correction the analyzer does not trust.
#:
#: Below the default issue floor, so these are recorded and counted but not
#: shown. That is the point: they are the cases where a misspelling and an
#: unlisted name are indistinguishable, and showing them is how a student
#: learns to ignore the panel.
UNTRUSTED_CONFIDENCE = 0.45


@lru_cache(maxsize=1)
def _checker() -> Any | None:
    """The dictionary, loaded once per process.

    Roughly a megabyte of word frequencies. Loading it per submission would
    put a file read and a JSON parse on the request path for a lookup table
    that never changes.
    """
    try:
        from spellchecker import SpellChecker
    except ImportError:  # pragma: no cover - exercised through the fake in tests
        logger.warning(
            "pyspellchecker is not installed; spelling analysis is unavailable. "
            "Install it with: pip install pyspellchecker"
        )
        return None

    return SpellChecker(distance=2)


class SpellingAnalyzer:
    """Finds misspellings, and works hard not to find anything else."""

    name = "spelling"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def warm_up(self) -> None:
        """Load the dictionary during boot.

        A megabyte of word frequencies parsed on first use otherwise lands on
        whichever student submits first after a restart, and counts against
        their request rather than against startup — the same reason the OCR
        providers and the language model are warmed.

        A lookup *and* a correction, not just a construction. Both load
        lazily and separately: warming only the lookup leaves a quarter of a
        second of candidate machinery still sitting on the first student to
        misspell anything. Measured, not assumed — see the perf budget.
        """
        checker = _checker()
        if checker is not None:
            checker.unknown(["warmup"])
            checker.correction("wramup")

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        checker = _checker()
        if checker is None:
            return AnalyzerOutput(
                status=AnalyzerStatus.UNAVAILABLE,
                detail="No spelling dictionary is installed on this server.",
            )

        exempt = _exemptions(ctx)
        candidates = [t for t in real_words(ctx.doc) if _is_checkable(t, exempt)]

        if not candidates:
            # An answer of numbers and proper nouns. Reporting 0% accuracy
            # would be a judgement about spelling that was never tested.
            return AnalyzerOutput(metrics={"words_checked": 0.0})

        unknown = checker.unknown([t.text.lower() for t in candidates])
        issues = [
            issue
            for token in candidates
            if token.text.lower() in unknown
            for issue in (_issue_for(ctx, token, checker),)
            if issue is not None
        ]

        checked = len(candidates)

        # Scored on what would actually be shown. An issue the analyzer is not
        # confident enough to display is not one it should mark a student
        # down for — saying "we are not sure this is a misspelling" and then
        # counting it as one is the contradiction this avoids.
        floor = self.settings.ASSESSMENT_ISSUE_CONFIDENCE_FLOOR
        counted = [i for i in issues if i.confidence >= floor]
        accuracy = round(100.0 * (checked - len(counted)) / checked, 2)

        return AnalyzerOutput(
            issues=tuple(issues),
            score=scale(accuracy, ACCURACY_FLOOR, ACCURACY_CEILING),
            metrics={
                "words_checked": float(checked),
                "misspelled_words": float(len({i.original_text.lower() for i in counted})),
                "misspelling_count": float(len(counted)),
                "uncertain_count": float(len(issues) - len(counted)),
                "accuracy_percentage": accuracy,
                "exempted_terms": float(len(exempt)),
            },
        )


def _is_checkable(token: Token, exempt: frozenset[str]) -> bool:
    """Whether a token is a word this checker has any business judging."""
    if not token.is_alpha or len(token.text) < MIN_LENGTH:
        return False
    if token.like_url or token.like_email or token.like_num:
        return False
    if _is_name(token):
        return False
    return token.text.lower() not in exempt


def _is_name(token: Token) -> bool:
    """Whether a token is a name rather than a word to check.

    Deliberately **not** ``pos_ == "PROPN"``. The tagger falls back to PROPN
    for any word it does not know, which is exactly what a misspelling is —
    "gradualy" comes back tagged PROPN, and trusting that tag would exempt
    every typo in the answer. The signal that makes a word a misspelling is
    the signal that makes the tagger guess it is a name.

    Two things do carry information: the entity recogniser, which is a
    separate model rather than a fallback, and capitalisation *away from the
    start of a sentence*, where a capital is a choice rather than a
    convention. A lower-case word is never treated as a name — and one that is
    genuinely an unlisted proper noun still ends up reported at a confidence
    the default floor suppresses.
    """
    if token.ent_type_:
        return True
    return bool(token.text[:1].isupper()) and token.i != token.sent.start


def _exemptions(ctx: AssessmentContext) -> frozenset[str]:
    """Every word this submission has a reason to contain.

    Three sources, all specific to the submission rather than to English:
    the vocabulary the answer is marked against, the words the student
    actually matched, and everything written on the chart they were shown.
    """
    words: set[str] = set()

    for term in ctx.targets.terms:
        words |= words_in(term.term)
        words |= words_in(term.lemma)

    # The inflections the detector matched. A student who wrote "plateaued"
    # and was credited for it must not then be told it is misspelled.
    for detected in ctx.detection.detected:
        for form in detected.matched_forms:
            words |= words_in(form)

    words |= chart_words(ctx.chart_data)

    return frozenset(w for w in words if w)


def _issue_for(ctx: AssessmentContext, token: Token, checker: Any) -> AssessmentIssue | None:
    """One misspelling, with a correction where there is a confident one."""
    word = token.text.lower()
    start, end = token_span(ctx, token)

    correction = checker.correction(word)
    if correction is None or correction == word:
        # Unknown, and the dictionary has nothing to offer. Most often a name
        # or a domain term the exemptions missed, so this is reported quietly
        # and at a confidence the default floor suppresses — visible in the
        # suppressed count, not on the student's screen.
        return AssessmentIssue(
            category=IssueCategory.SPELLING,
            subtype="unrecognised_word",
            severity=IssueSeverity.LOW,
            original_text=token.text,
            explanation=(
                f"“{token.text}” is not in the dictionary. If it is a name or a technical "
                f"term, ignore this."
            ),
            start=start,
            end=end,
            confidence=0.45,
            source="dictionary",
        )

    distance = checker.distance if hasattr(checker, "distance") else 2
    edits = _edit_distance(word, correction, limit=distance)
    confident = edits <= CONFIDENT_EDIT_DISTANCE
    suggestion = _match_case(token.text, correction)

    # A capital at the start of a sentence is a convention, so it says nothing
    # about whether the word is a name — and the entity recogniser has already
    # declined to claim it. "Sylhet" and "Gradualy" are the same shape to
    # everything this analyzer can see, and telling a student their own city
    # is a misspelling of "Sleet" costs more than the typo it might have
    # caught. Reported below the floor rather than dropped, so the suppressed
    # count still shows it happened.
    ambiguous = token.text[:1].isupper()

    return AssessmentIssue(
        category=IssueCategory.SPELLING,
        subtype="misspelling",
        severity=IssueSeverity.LOW if ambiguous or not confident else IssueSeverity.MEDIUM,
        original_text=token.text,
        suggested_text=suggestion,
        explanation=(
            f"“{token.text}” looks like a misspelling of “{suggestion}”."
            if not ambiguous
            else f"“{token.text}” is not in the dictionary — did you mean “{suggestion}”? "
            f"If it is a name, ignore this."
        ),
        start=start,
        end=end,
        confidence=UNTRUSTED_CONFIDENCE if ambiguous else (0.9 if confident else 0.65),
        source="dictionary",
    )


def _edit_distance(a: str, b: str, *, limit: int = 2) -> int:
    """Levenshtein distance, short-circuited at ``limit``.

    Only the difference between "one keystroke out" and "a different word
    entirely" matters here, and that decides the severity — so the exact
    distance beyond the limit is never needed.
    """
    if abs(len(a) - len(b)) > limit:
        return limit + 1

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (ca != cb),
                )
            )
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def _match_case(original: str, correction: str) -> str:
    """Give the suggestion the student's own capitalisation.

    Being told to replace "Gradualy" with "gradually" at the start of a
    sentence is a correction that introduces an error.
    """
    if original.isupper():
        return correction.upper()
    if original[:1].isupper():
        return correction.capitalize()
    return correction


__all__ = ["SpellingAnalyzer"]
