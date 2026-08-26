"""The comparison itself: measurements placed beside earlier measurements.

Everything in this module is a pure function over rows the repository has
already read, and **nothing it produces is ever stored**. That is not a
performance choice. A stored comparison is a stored judgement with a
timestamp: it goes stale the moment the next submission lands, it survives the
deletion of the submission it was drawn from, and it is the artefact that
would end up quoted in a meeting. Computing live means the answer always
reflects the whole history as it currently stands, and there is nothing to
quote but the numbers themselves.

Three things this module deliberately does not have, each of which was asked
for at some point and each of which is the same mistake:

* **No composite.** The measures are never combined into one figure. A single
  number across dimensions is orderable, and its components cannot be
  recovered from it — which is what a risk score is.
* **No threshold, flag or notability test.** There is no ground truth here to
  calibrate one against, and six measures across a cohort will produce
  "unusual" readings by chance at a predictable rate. Values are reported;
  whether one matters is a teacher's judgement.
* **No ordering of students.** Nothing here sorts or ranks. A list of students
  ordered by how much their writing changed is an accusation with the wording
  removed.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.assessment.consistency.gating import partition
from app.assessment.consistency.profile import COMPARED_MEASURES, ProfileRow
from app.core.config import Settings

#: The comparison's own version, reported with every result.
#:
#: The assessment fingerprint on a row records how the *measurements* were
#: produced. It cannot record how they were compared, because the comparison
#: happens at read time and is not stored anywhere — so two teachers looking
#: at the same submissions a release apart could otherwise see different
#: numbers with nothing to say why. Bump this when the arithmetic below
#: changes.
CONSISTENCY_MODEL_VERSION = "1.0.0"


class ConsistencyDisabledError(RuntimeError):
    """Raised when the comparison layer is called on a deployment with it off.

    Not a silent empty result: an empty comparison and a switched-off one look
    identical to a caller, and only one of them is a fact about the student.
    """


def require_enabled(settings: Settings) -> None:
    """The single door into this package. Sprint 20's endpoint calls it first."""
    if not settings.CONSISTENCY_ANALYTICS_ENABLED:
        raise ConsistencyDisabledError(
            "Writing-consistency analytics are not enabled on this deployment."
        )


@dataclass(frozen=True, slots=True)
class Baseline:
    """What one measure has looked like for this student until now."""

    measure: str
    mean: float
    #: Population standard deviation across the comparable prior submissions.
    #: Reported so a reader can see how settled the measure is; never divided
    #: into anything, because that would be a z-score and a z-score invites a
    #: threshold.
    spread: float
    #: How many submissions it was actually built from. Printed beside every
    #: figure — a mean over three and a mean over eleven are different
    #: evidence, and one without the count reads as though they were not.
    n: int
    lowest: float
    highest: float


@dataclass(frozen=True, slots=True)
class Change:
    """One measure now, beside what it has been."""

    measure: str
    #: ``None`` when this submission has no figure for the measure — the
    #: analyzer did not run, or no engine is configured. Never zero.
    current: float | None
    #: ``None`` when there are too few comparable prior submissions. This is
    #: the normal state for most of a term, and it is rendered as "no baseline
    #: yet" — never as zero, and never as "consistent".
    baseline: Baseline | None
    #: Current minus the baseline mean, in the measure's own units. Raw
    #: arithmetic a teacher would do by hand, not a normalised distance.
    difference: float | None


@dataclass(frozen=True, slots=True)
class StudentComparison:
    """One submission's measures, against the student's own earlier work."""

    model_version: str
    changes: tuple[Change, ...]
    #: Prior submissions that passed every comparability gate.
    compared_count: int
    #: Prior submissions considered, gates included. ``compared_count`` out of
    #: this is the honest headline.
    considered_count: int
    #: How many were excluded, by reason. Shown, never hidden.
    excluded: Mapping[str, int] = field(default_factory=dict)

    @property
    def has_baseline(self) -> bool:
        return any(change.baseline is not None for change in self.changes)


def compare_student(
    current: ProfileRow,
    priors: list[ProfileRow],
    *,
    min_words: int,
    min_baseline: int,
) -> StudentComparison:
    """Place one submission beside the same student's earlier submissions.

    ``priors`` are that student's other assessed submissions. Rows at or after
    ``current`` are dropped: a baseline is what came *before*, and including
    later work would let a teacher's view of an old submission change every
    time the student writes another one.

    "Before" is decided on the timestamp *and* the submission id, which is the
    order the repository already returns rows in. The tie-break is not
    decoration: ``assessment_details.created_at`` defaults to the transaction
    clock, so two assessments written in one transaction — or two workers
    finishing inside the same tick — carry the same instant, and on the
    timestamp alone neither would be earlier than the other. Both would then
    drop out of each other's baselines and simply vanish from the history.
    Pairing the id makes the relation a total order, so of any two distinct
    assessments exactly one is earlier and a baseline is always well defined.
    """
    here = (current.assessed_at, current.submission_id)
    earlier = [row for row in priors if (row.assessed_at, row.submission_id) < here]
    comparable_rows, excluded = partition(current, earlier, min_words=min_words)

    changes = tuple(
        _change(current, comparable_rows, measure, min_baseline=min_baseline)
        for measure in COMPARED_MEASURES
    )

    return StudentComparison(
        model_version=CONSISTENCY_MODEL_VERSION,
        changes=changes,
        compared_count=len(comparable_rows),
        considered_count=len(earlier),
        excluded=dict(excluded),
    )


def _change(
    current: ProfileRow,
    comparable_rows: list[ProfileRow],
    measure: str,
    *,
    min_baseline: int,
) -> Change:
    now = current.value(measure)
    base = baseline(comparable_rows, measure, min_baseline=min_baseline)

    difference = None
    if now is not None and base is not None:
        difference = round(now - base.mean, 4)

    return Change(measure=measure, current=now, baseline=base, difference=difference)


def baseline(
    rows: list[ProfileRow],
    measure: str,
    *,
    min_baseline: int,
) -> Baseline | None:
    """What this measure has been, or ``None`` if there is not enough to say.

    Rows with no figure for the measure are absent from the count rather than
    averaged in as noughts — a deployment with no grammar engine has no
    grammar baseline, which is a different thing from a baseline of zero.

    The floor is applied per measure, not per submission: on a server without
    grammar, a student can have a settled lexical-diversity baseline and no
    grammar baseline at all, and reporting the first is right.
    """
    values = [value for row in rows if (value := row.value(measure)) is not None]

    if len(values) < min_baseline:
        return None

    return Baseline(
        measure=measure,
        mean=round(statistics.fmean(values), 4),
        # Population, not sample: these are all of the student's comparable
        # submissions, not a sample drawn from more of them.
        spread=round(statistics.pstdev(values), 4),
        n=len(values),
        lowest=round(min(values), 4),
        highest=round(max(values), 4),
    )


@dataclass(frozen=True, slots=True)
class Distribution:
    """How one measure is spread across a class.

    A distribution and nothing else. There is deliberately no per-student
    breakdown on this object and no ordering anywhere near it: a class view
    exists to answer "is this cohort's sentence complexity moving", not to
    say which students sit furthest from the middle.
    """

    measure: str
    median: float
    q1: float
    q3: float
    #: Distinct students represented, not submissions. A measure carried by
    #: one prolific student is not a class distribution.
    students: int
    submissions: int


def class_distribution(
    rows: list[ProfileRow],
    measure: str,
    *,
    min_samples: int,
) -> Distribution | None:
    """The spread of one measure across a class, or ``None`` if too few.

    Suppressed below ``min_samples`` distinct students. With three students a
    "distribution" identifies individuals and means nothing statistically —
    and the two failures compound, because the figure is both unreliable and
    re-identifying at exactly the same sizes.
    """
    values: list[float] = []
    students: set[object] = set()

    for row in rows:
        value = row.value(measure)
        if value is None:
            continue
        values.append(value)
        students.add(row.user_id)

    if len(students) < min_samples:
        return None

    quartiles = statistics.quantiles(values, n=4) if len(values) > 1 else [values[0]] * 3

    return Distribution(
        measure=measure,
        median=round(statistics.median(values), 4),
        q1=round(quartiles[0], 4),
        q3=round(quartiles[2], 4),
        students=len(students),
        submissions=len(values),
    )


__all__ = [
    "CONSISTENCY_MODEL_VERSION",
    "Baseline",
    "Change",
    "ConsistencyDisabledError",
    "Distribution",
    "StudentComparison",
    "baseline",
    "class_distribution",
    "compare_student",
    "require_enabled",
]
