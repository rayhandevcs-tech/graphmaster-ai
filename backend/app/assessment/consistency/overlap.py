"""How much of one attempt is carried over verbatim from an earlier one.

The most explainable measure in the feature, and the least inferential: both
texts are the student's own, both are already in front of the teacher, and the
evidence is the words themselves rather than a statistic about them.

**High overlap is not a finding.** A new submission is how a student
re-attempts a graph, so keeping most of the previous attempt is the ordinary
shape of a revision — this answers "did they revise or resubmit", which is the
first thing a teacher wants to know when marking attempt three. It is reported
as a proportion and never labelled, never thresholded, and never compared
against another student: this module only ever takes two texts written by the
same person.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Words per shingle. Five is long enough that ordinary phrasing about charts
#: — "the number of visitors to" — does not register as reuse, and short
#: enough to catch a sentence that was kept with two words changed.
SHINGLE_SIZE = 5

_WORD = re.compile(r"[0-9a-z]+")


@dataclass(frozen=True, slots=True)
class Overlap:
    """What one attempt kept from the one before it."""

    #: 0–100: the share of *this* attempt's phrasing that also appears in the
    #: earlier one. Containment rather than a symmetric similarity, because
    #: the question is about the new answer: an attempt that keeps everything
    #: and adds a paragraph has still kept everything.
    retained_percentage: float
    shingles: int
    shared: int


def self_overlap(current: str, previous: str) -> Overlap | None:
    """Compare a student's attempt with their own earlier one.

    ``None`` when either text is too short to shingle — under five words there
    is nothing to compare, and reporting 0% would read as "they rewrote it
    completely" rather than "we could not tell".
    """
    current_shingles = _shingles(current)
    previous_shingles = _shingles(previous)

    if not current_shingles or not previous_shingles:
        return None

    shared = len(current_shingles & previous_shingles)
    return Overlap(
        retained_percentage=round(shared / len(current_shingles) * 100.0, 2),
        shingles=len(current_shingles),
        shared=shared,
    )


def _shingles(text: str) -> frozenset[tuple[str, ...]]:
    """Overlapping word n-grams, case-folded and stripped of punctuation.

    This is the one place in the platform that lowercases and drops
    punctuation, and it is deliberate rather than an oversight of the rule
    that normalisation must not. That rule protects two things: case feeds the
    part-of-speech tagger, and punctuation feeds sentence segmentation. No
    tagger and no segmenter runs here, nothing maps back to an offset in the
    original, and a student who kept a sentence but repunctuated it has still
    kept the sentence.
    """
    words = _WORD.findall(text.casefold())
    if len(words) < SHINGLE_SIZE:
        return frozenset()
    return frozenset(
        tuple(words[i : i + SHINGLE_SIZE]) for i in range(len(words) - SHINGLE_SIZE + 1)
    )


__all__ = ["SHINGLE_SIZE", "Overlap", "self_overlap"]
