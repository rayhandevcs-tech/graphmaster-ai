"""The assembled outcome of one assessment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.assessment.claims import GraphClaim
from app.assessment.issues import AssessmentIssue
from app.assessment.protocol import AnalyzerOutput
from app.models.enums import AnalyzerAudience, AnalyzerStatus, IssueCategory


@dataclass(frozen=True, slots=True)
class AssessmentResult:
    """What every analyzer found, ready to persist or serialise.

    Deliberately *not* a score. This object carries no field that
    :func:`app.nlp.scoring.build_score` reads, and none that the gamification
    service reads — the separation is the whole point of the design and is
    asserted by ``tests/unit/test_assessment_isolation.py``.
    """

    version: str
    #: Keyed by analyzer name, in the order they ran.
    analyzers: dict[str, AnalyzerOutput]
    #: Filtered, deduplicated and ordered for reading.
    issues: tuple[AssessmentIssue, ...]
    #: Issues that were found but fell below the confidence floor. Counted
    #: rather than discarded silently: a floor set too high is invisible
    #: otherwise, and this is the number that says so.
    suppressed_count: int = 0
    #: Categories where the per-submission cap dropped issues, so a truncated
    #: list can be shown as truncated instead of as complete.
    truncated_categories: tuple[str, ...] = ()
    #: Every claim about the chart that was checked, correct ones included.
    claims: tuple[GraphClaim, ...] = ()
    #: Who may see each analyzer's output. Recorded at assessment time rather
    #: than read at display time, so a rollout stage that changed since a
    #: submission was marked cannot retroactively reveal what was dark.
    audiences: dict[str, AnalyzerAudience] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        """Issues that assert a mistake — everything above ``INFO``.

        A style preference is deliberately not counted: telling a student they
        made nine mistakes when four of them were suggestions is the failure
        FR-5 rules out.
        """
        return sum(1 for i in self.issues if i.is_mistake)

    @property
    def ran_analyzers(self) -> tuple[str, ...]:
        return tuple(name for name, out in self.analyzers.items() if out.ran)

    @property
    def failed_analyzers(self) -> tuple[str, ...]:
        """Analyzers that broke — as distinct from ones not installed here."""
        return tuple(
            name for name, out in self.analyzers.items() if out.status is AnalyzerStatus.FAILED
        )

    @property
    def is_complete(self) -> bool:
        """Whether every analyzer that was asked to run actually did."""
        return not any(out.status is AnalyzerStatus.FAILED for out in self.analyzers.values())

    def for_audience(self, audience: AnalyzerAudience) -> AssessmentResult:
        """The same result, with everything this audience may not see removed.

        A student's copy of a result is *built* without the withheld analyzers
        rather than serialised with them omitted: a filtered object cannot leak
        through a field someone adds to a schema later.

        Teachers see everything except what is still dark; students see only
        what has been promoted all the way. Nothing is hidden from an
        administrator that is hidden from a teacher — an administrator's extra
        power is over accounts and content, not over another student's writing.
        """
        if audience is AnalyzerAudience.TEACHER:
            visible = {
                name for name, stage in self.audiences.items() if stage is not AnalyzerAudience.DARK
            }
        elif audience is AnalyzerAudience.STUDENT:
            visible = {
                name for name, stage in self.audiences.items() if stage is AnalyzerAudience.STUDENT
            }
        else:  # DARK sees everything; it is the internal, unfiltered view.
            return self

        return AssessmentResult(
            version=self.version,
            analyzers={name: out for name, out in self.analyzers.items() if name in visible},
            issues=tuple(i for i in self.issues if i.analyzer in visible),
            claims=self.claims if "graph_accuracy" in visible else (),
            # Counted over what was withheld too: the numbers describe the
            # assessment that ran, not the slice being shown.
            suppressed_count=self.suppressed_count,
            truncated_categories=self.truncated_categories,
            audiences={name: self.audiences[name] for name in visible},
        )

    def issues_for(self, category: IssueCategory) -> tuple[AssessmentIssue, ...]:
        return tuple(i for i in self.issues if i.category is category)

    def counts_by_category(self) -> dict[str, int]:
        """Issue counts for every category, including the empty ones.

        Zeros are included on purpose: "no spelling issues" is a finding, and
        a missing key in a chart reads as missing data rather than as none.
        """
        counts = {category.value: 0 for category in IssueCategory}
        for issue in self.issues:
            counts[issue.category.value] += 1
        return counts

    def scores(self) -> dict[str, float | None]:
        """Each analyzer's diagnostic score, ``None`` where it did not run."""
        return {name: out.score for name, out in self.analyzers.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_version": self.version,
            "is_complete": self.is_complete,
            "issue_count": len(self.issues),
            "error_count": self.error_count,
            "suppressed_count": self.suppressed_count,
            "truncated_categories": list(self.truncated_categories),
            "counts_by_category": self.counts_by_category(),
            "claims": [c.to_dict() for c in self.claims],
            "scores": self.scores(),
            "analyzers": {name: out.to_dict() for name, out in self.analyzers.items()},
            "issues": [i.to_dict() for i in self.issues],
        }


__all__ = ["AssessmentResult"]
