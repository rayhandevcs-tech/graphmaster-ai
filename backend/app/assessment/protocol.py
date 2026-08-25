"""What an analyzer is, and what it is given.

The contract is deliberately narrow. An analyzer receives one immutable
context and returns one value; it cannot reach the database, the request, or
the other analyzers' internals. That is what keeps every analyzer testable
without HTTP — the same property that lets ``app.nlp`` be run over a corpus in
an offline research script.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from app.assessment.claims import GraphClaim
from app.assessment.issues import AssessmentIssue
from app.models.enums import AnalyzerStatus, GraphType
from app.nlp.detector import DetectionResult
from app.nlp.normalise import NormalisedText
from app.nlp.terms import CompiledTargets
from app.nlp.writing import WritingQuality

if TYPE_CHECKING:  # pragma: no cover
    from spacy.tokens import Doc


@dataclass(frozen=True, slots=True)
class AssessmentContext:
    """Everything an analyzer may look at.

    ``doc`` is the crux of the performance story. Parsing is the expensive
    step in an analysis and it has already happened by the time this is built,
    so an analyzer that reads this ``Doc`` costs a traversal rather than a
    parse. An analyzer that calls ``get_nlp()`` itself has doubled the cost of
    the whole pipeline and should be rejected in review.

    ``detection`` and ``writing`` are the existing engine's own output, passed
    in so a later analyzer can build on what the vocabulary detector already
    found rather than finding it a second way. Two detectors that disagree
    about the same sentence make the result indefensible to a student.
    """

    #: The student's answer exactly as submitted. Issue offsets index this.
    text: str
    #: The parsed document, over the normalised text. Shared; never re-parsed.
    doc: Doc
    #: Carries the index map from normalised positions back into ``text``.
    normalised: NormalisedText
    targets: CompiledTargets
    detection: DetectionResult
    writing: WritingQuality
    #: The graph's Chart.js data, when the analysis is for a specific graph.
    #: A plain mapping rather than the API schema: the engine stays free of
    #: the schema layer so it can be driven from a script.
    chart_data: Mapping[str, Any] | None = None
    graph_type: GraphType | None = None

    @property
    def word_count(self) -> int:
        return self.writing.word_count


@dataclass(frozen=True, slots=True)
class AnalyzerOutput:
    """One analyzer's findings, or its reason for having none.

    ``status`` distinguishes the three ways an empty issue list can happen,
    which a bare list cannot: the analyzer ran and found nothing, the analyzer
    is not configured on this server, or the analyzer broke. A UI that cannot
    tell them apart will tell a student their grammar is perfect on a server
    with no grammar checker installed.
    """

    status: AnalyzerStatus = AnalyzerStatus.OK
    issues: tuple[AssessmentIssue, ...] = ()
    #: Named measurements this analyzer produced — the evidence behind its
    #: score, exposed for the same reason ``writing_breakdown`` is: a score a
    #: teacher cannot interrogate is a score they cannot defend.
    metrics: Mapping[str, float] = field(default_factory=dict)
    #: 0–100, diagnostic only. Never an input to the final score.
    score: float | None = None
    #: Why, when the status is not ``OK``. Shown to an operator, not a student.
    detail: str | None = None
    #: Statements about the chart that were checked against it.
    #:
    #: Specific to the graph-accuracy analyzer, and on the shared output
    #: rather than in a channel of its own because the supervisor is the only
    #: thing that collects analyzer results. A parallel route for one
    #: analyzer's extra output would be a second thing to keep in step.
    claims: tuple[GraphClaim, ...] = ()
    #: Wall-clock cost, filled in by the supervisor.
    duration_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.score is not None and not 0.0 <= self.score <= 100.0:
            raise ValueError(f"Analyzer score {self.score} is outside 0–100.")

    @property
    def ran(self) -> bool:
        return self.status is AnalyzerStatus.OK

    def with_duration(self, duration_ms: float) -> AnalyzerOutput:
        return replace(self, duration_ms=round(duration_ms, 3))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "issue_count": len(self.issues),
            "score": self.score,
            "detail": self.detail,
            "duration_ms": self.duration_ms,
            "claim_count": len(self.claims),
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()},
        }


UNAVAILABLE = AnalyzerOutput(status=AnalyzerStatus.UNAVAILABLE)


@runtime_checkable
class Analyzer(Protocol):
    """One diagnostic pass over an answer.

    Implementations must be **pure and synchronous**: no I/O except through an
    explicitly injected provider, and no mutation of the context. The
    supervisor calls them one at a time and treats any exception as that
    analyzer's failure alone.
    """

    #: Stable identifier, used in configuration and stored on every issue.
    name: str

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput: ...


__all__ = [
    "UNAVAILABLE",
    "Analyzer",
    "AnalyzerOutput",
    "AssessmentContext",
]
