"""Writing consistency: how one student's own writing moves over time.

Teacher-facing, diagnostic, and structurally unable to reach a student. This
package is the *comparison* half of the feature; the measurement half is
:mod:`app.assessment.analyzers.writing_profile`, which runs at assessment time
and writes numbers into the existing assessment row.

What this is, precisely
-----------------------

A longitudinal view of quantities the platform already computes. It is not a
new kind of judgement about writing — it is the existing measurements plotted
against time and against the student's own earlier work.

What it is not, and what no part of it computes internally: a probability that
text was machine-generated, an authorship decision, a risk or integrity or
suspicion value under any name, a comparison between two different students,
or a flag whose meaning is "look at this one". The last is the one that has to
be said out loud, because a review flag with no label attached is still a
verdict — it says *this student, not those students*.

Two facts that govern how any of it may be presented
----------------------------------------------------

**The platform causes the changes it measures.** Its purpose is to raise
target-vocabulary use and writing quality, and it names missing terms in the
feedback on every scored submission. A student who is taught to use
*fluctuate* and then uses it has shifted their vocabulary profile because the
system told them to. Among students the course succeeds with, large change is
the ordinary case.

**A settled profile is not evidence of anything.** A student assisted
uniformly from their first submission has a perfectly stable baseline, because
the baseline is itself assisted. These measures cannot detect uniform
assistance — not poorly, but in principle, since they measure change and there
is none. Any surface built on this package has to say so, or "consistent" will
be read as "cleared", which is a harm in the opposite direction from the one
the constraints guard against.

Layout
------

``profile``   Reading a stored profile back, and deciding if it is usable.
``gating``    Which pairs of submissions may be compared at all.
``compare``   Baselines, changes and class distributions. Stores nothing.
``overlap``   How much of one attempt is carried over from an earlier one.
"""

from __future__ import annotations

from app.assessment.consistency.compare import (
    CONSISTENCY_MODEL_VERSION,
    Baseline,
    Change,
    ConsistencyDisabledError,
    Distribution,
    StudentComparison,
    baseline,
    class_distribution,
    compare_student,
    require_enabled,
)
from app.assessment.consistency.gating import (
    REASONS,
    Exclusion,
    comparable,
    partition,
    segments,
)
from app.assessment.consistency.overlap import SHINGLE_SIZE, Overlap, self_overlap
from app.assessment.consistency.profile import (
    COLUMN_MEASURES,
    COMPARED_MEASURES,
    PROFILE_MEASURES,
    Profile,
    ProfileRow,
)

__all__ = [
    "COLUMN_MEASURES",
    "COMPARED_MEASURES",
    "CONSISTENCY_MODEL_VERSION",
    "PROFILE_MEASURES",
    "REASONS",
    "SHINGLE_SIZE",
    "Baseline",
    "Change",
    "ConsistencyDisabledError",
    "Distribution",
    "Exclusion",
    "Overlap",
    "Profile",
    "ProfileRow",
    "StudentComparison",
    "baseline",
    "class_distribution",
    "comparable",
    "compare_student",
    "partition",
    "require_enabled",
    "segments",
    "self_overlap",
]
