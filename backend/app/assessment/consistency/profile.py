"""One submission's stored profile, and the row it was read back from.

The analyzer writes measurements into
``assessment_details.analyzer_status['writing_profile']['metrics']``. This
module is what reads them back and decides whether what it found is usable.

Nothing here compares anything. These are the inputs a comparison is made
from, and keeping the parsing separate from the arithmetic is what lets a
malformed blob be treated as *absent* rather than as a fault: a profile
written by an older release with a different measure set must cost a teacher
one point on a chart, not their page.
"""

from __future__ import annotations

import datetime as dt
import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.assessment.analyzers.writing_profile import MEASURES

#: Measures held in the profile blob.
PROFILE_MEASURES: tuple[str, ...] = MEASURES

#: Measures read from ``assessment_details`` columns instead.
#:
#: Mechanical accuracy already has a home — the spelling and grammar analyzers
#: write these columns, and the profile analyzer cannot see another analyzer's
#: output anyway. Re-measuring them would put one fact in two places and let
#: the two disagree.
COLUMN_MEASURES: tuple[str, ...] = ("spelling_score", "grammar_score")

#: Everything a trend may be drawn for.
#:
#: Deliberately a flat tuple with no weights and no grouping. There is no
#: combination of these into a single figure, anywhere in this package: a
#: composite across dimensions is a risk score with a friendly name — one
#: number, orderable, whose components cannot be recovered from it.
COMPARED_MEASURES: tuple[str, ...] = PROFILE_MEASURES + COLUMN_MEASURES


@dataclass(frozen=True, slots=True)
class Profile:
    """The measurements from one submission, once they are known to be sound."""

    measures: Mapping[str, float]
    word_count: int
    sentence_count: int

    @classmethod
    def from_metrics(cls, metrics: Any) -> Profile | None:
        """Parse a stored metrics blob, or answer ``None``.

        ``None`` for every kind of unusable, without distinguishing them:
        absent, written by a release with a different measure set, corrupt,
        or carrying a NaN from arithmetic that went wrong years ago. The
        caller's question is only ever "can this take part in a comparison",
        and the honest answer to all four is no.

        Never raises. A profile is read while a teacher is looking at a page,
        and one bad row in a term's history must not be able to empty it.
        """
        if not isinstance(metrics, Mapping):
            return None

        values: dict[str, float] = {}
        for key in (*PROFILE_MEASURES, "word_count", "sentence_count"):
            number = _finite(metrics.get(key))
            if number is None:
                return None
            values[key] = number

        return cls(
            measures={key: values[key] for key in PROFILE_MEASURES},
            word_count=int(values["word_count"]),
            sentence_count=int(values["sentence_count"]),
        )


@dataclass(frozen=True, slots=True)
class ProfileRow:
    """One assessed submission, with everything a comparability gate reads.

    Assembled by the repository from one query. The gates need the graph type,
    the input method and the assessment version as much as they need the
    measurements, and a row that carried only the numbers would force a second
    read per comparison.

    ``answer_text`` is deliberately **not** here. Self-overlap is the one
    measure that needs it, it is only ever computed between a student's own
    attempts at one graph, and carrying every answer in a class-wide series
    would read a cohort's writing into memory to draw a chart that does not
    use it.
    """

    submission_id: uuid.UUID
    user_id: uuid.UUID
    graph_id: uuid.UUID
    graph_type: str
    input_method: str
    assessment_version: str
    assessed_at: dt.datetime
    profile: Profile | None
    spelling_score: float | None
    grammar_score: float | None

    @property
    def has_profile(self) -> bool:
        return self.profile is not None

    def value(self, measure: str) -> float | None:
        """This row's figure for one measure, or ``None`` where there is none.

        ``None`` means *not measured here* — the analyzer did not run, the
        answer was too short to profile, or no grammar engine is configured on
        this deployment. It is never zero: a class whose grammar was never
        checked is not a class that scored nothing, and a zero would sort them
        below one that genuinely struggled.
        """
        if measure in COLUMN_MEASURES:
            stored = getattr(self, measure)
            return None if stored is None else float(stored)
        if self.profile is None:
            return None
        return self.profile.measures.get(measure)


def _finite(value: Any) -> float | None:
    """A real number, or ``None`` for anything that is not one.

    ``bool`` is rejected explicitly: it is a subclass of ``int``, and a
    ``True`` that arrived where a measurement belongs is corrupt data wearing
    a plausible type.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


__all__ = [
    "COLUMN_MEASURES",
    "COMPARED_MEASURES",
    "PROFILE_MEASURES",
    "Profile",
    "ProfileRow",
]
