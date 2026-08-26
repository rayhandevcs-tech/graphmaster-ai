"""Who may see which analyzer's output.

One predicate, used by both paths that need it: the in-memory
:class:`~app.assessment.result.AssessmentResult` a scoring request has just
built, and the stored row a teacher opens three weeks later. They must not
drift apart — a rule that is right in one and wrong in the other is the shape
of a leak nobody notices, because the live path is the one covered by every
engine test and the stored path is the one a person actually reads.

**The audiences come from the row, never from the current configuration.** A
rollout stage that has moved since the work was marked would otherwise
retroactively reveal what was dark when it was marked, which is the one thing
a staged rollout exists to prevent.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.enums import AnalyzerAudience


def visible_analyzers(
    audiences: Mapping[str, AnalyzerAudience],
    viewer: AnalyzerAudience,
) -> set[str]:
    """The analyzer names ``viewer`` may be shown.

    Teachers see everything except what is still dark; students see only what
    has been promoted all the way. ``DARK`` as a *viewer* is the internal,
    unfiltered view — it is not a role anybody logs in as, and nothing is
    hidden from an administrator that is hidden from a teacher, because an
    administrator's extra power is over accounts and content rather than over
    another student's writing.

    An analyzer with no recorded audience is not visible to anyone. That is
    not an edge case to tidy away: it is what an assessment written before the
    audience map existed looks like, and withholding it is the safe reading.
    """
    if viewer is AnalyzerAudience.TEACHER:
        return {name for name, stage in audiences.items() if stage is not AnalyzerAudience.DARK}
    if viewer is AnalyzerAudience.STUDENT:
        return {name for name, stage in audiences.items() if stage is AnalyzerAudience.STUDENT}
    return set(audiences)


def stored_audiences(raw: Mapping[str, Any] | None) -> dict[str, AnalyzerAudience]:
    """Parse the audience map frozen onto an assessment row.

    A value this build does not recognise resolves to ``DARK`` — the most
    restrictive reading, not the most convenient one. An unparseable stage
    means the row cannot say who was meant to see that analyzer, and the
    honest answer to "who may see this" when the record does not say is
    nobody.

    Never raises. This runs while a teacher is opening a page.
    """
    if not isinstance(raw, Mapping):
        return {}

    parsed: dict[str, AnalyzerAudience] = {}
    for name, stage in raw.items():
        if not isinstance(name, str):
            continue
        try:
            parsed[name] = AnalyzerAudience(stage)
        except ValueError:
            parsed[name] = AnalyzerAudience.DARK
    return parsed


def analyzer_of(source: str) -> str:
    """The analyzer name out of an issue's ``analyzer`` or ``analyzer:provider``.

    The same split :attr:`AssessmentIssue.analyzer` performs, available here
    for the stored path where the issue is an ORM row rather than the frozen
    value object.
    """
    return source.split(":", 1)[0]


__all__ = ["analyzer_of", "stored_audiences", "visible_analyzers"]
