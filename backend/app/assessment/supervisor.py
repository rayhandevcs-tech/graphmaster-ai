"""Runs the analyzers, and absorbs their failures.

This module is the safety property the whole design rests on: **a broken
analyzer must not cost a student their submission.** Scoring already survives
a missing OCR engine and a missing language model by degrading rather than
refusing; a diagnostic pass has even less claim to take the request down with
it, because the student's score does not depend on it at all.

So every call into an analyzer goes through here, and every exception one can
raise becomes that analyzer's own ``FAILED`` outcome with the reason recorded.
There is no path by which an analyzer's exception reaches the caller.
"""

from __future__ import annotations

import time

from app.assessment import assessment_version
from app.assessment.claims import GraphClaim
from app.assessment.issues import AssessmentIssue, deduplicate, order_for_display
from app.assessment.protocol import Analyzer, AnalyzerOutput, AssessmentContext
from app.assessment.result import AssessmentResult
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.enums import AnalyzerStatus, IssueCategory

logger = get_logger(__name__)


def run_analyzers(
    analyzers: list[Analyzer],
    ctx: AssessmentContext,
    *,
    settings: Settings | None = None,
) -> AssessmentResult:
    """Run each analyzer in turn and assemble one result.

    Order matters only in that later analyzers may read earlier ones' output
    through the context; nothing here depends on it otherwise, so the list can
    be reordered by configuration without changing what any analyzer sees.
    """
    settings = settings or get_settings()

    outputs: dict[str, AnalyzerOutput] = {}
    collected: list[AssessmentIssue] = []
    claims: list[GraphClaim] = []

    for analyzer in analyzers:
        output = _run_one(analyzer, ctx, settings)
        outputs[analyzer.name] = output
        claims.extend(output.claims)
        # Stamped here rather than trusted from the analyzer: `source` is what
        # the audience filter and a false-positive audit both key on, so an
        # issue that forgot it would be unattributable.
        collected.extend(issue.from_analyzer(analyzer.name) for issue in output.issues)

    issues, suppressed, truncated = _select(collected, settings)

    return AssessmentResult(
        version=assessment_version(settings),
        analyzers=outputs,
        issues=tuple(issues),
        claims=tuple(claims),
        suppressed_count=suppressed,
        truncated_categories=truncated,
        audiences={name: settings.analyzer_audience(name) for name in outputs},
    )


def _run_one(analyzer: Analyzer, ctx: AssessmentContext, settings: Settings) -> AnalyzerOutput:
    """One analyzer, timed, with every failure mode caught.

    ``BaseException`` is deliberately *not* caught: a ``KeyboardInterrupt`` or
    a cancellation is the process being asked to stop, and swallowing it here
    would turn a shutdown into a hang.
    """
    started = time.perf_counter()
    try:
        output = analyzer.run(ctx)
    # Every failure mode an analyzer can produce is contained here.
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000
        logger.exception("Analyzer %s failed after %.1fms: %s", analyzer.name, elapsed, exc)
        return AnalyzerOutput(
            status=AnalyzerStatus.FAILED,
            # The exception type, not its message: a message can quote the
            # student's own text, and this string is bound for operator logs
            # and a teacher's screen.
            detail=f"{type(exc).__name__} while running {analyzer.name}",
        ).with_duration(elapsed)

    elapsed = (time.perf_counter() - started) * 1000

    if elapsed > settings.ASSESSMENT_ANALYZER_BUDGET_MS:
        # Recorded and logged, not killed. A CPU-bound Python call cannot be
        # preempted from another thread without leaving the interpreter in an
        # unpredictable state, so this is an observation rather than an
        # enforcement. Genuine cancellation belongs to whichever provider does
        # I/O — the grammar client's socket timeout — where it can be done
        # safely. See docs/architecture/10-assessment-architecture.md.
        logger.warning(
            "Analyzer %s took %.1fms, over its %.0fms budget",
            analyzer.name,
            elapsed,
            settings.ASSESSMENT_ANALYZER_BUDGET_MS,
        )

    return output.with_duration(elapsed)


def _select(
    issues: list[AssessmentIssue], settings: Settings
) -> tuple[list[AssessmentIssue], int, tuple[str, ...]]:
    """Apply the confidence floor and the per-category cap.

    Returns the issues to show, how many were suppressed by the floor, and
    which categories were truncated by the cap.
    """
    floor = settings.ASSESSMENT_ISSUE_CONFIDENCE_FLOOR
    above = [i for i in issues if i.confidence >= floor]
    suppressed = len(issues) - len(above)

    kept = deduplicate(above)

    cap = settings.ASSESSMENT_MAX_ISSUES_PER_CATEGORY
    by_category: dict[IssueCategory, list[AssessmentIssue]] = {}
    for issue in kept:
        by_category.setdefault(issue.category, []).append(issue)

    selected: list[AssessmentIssue] = []
    truncated: list[str] = []
    for category, bucket in by_category.items():
        if len(bucket) <= cap:
            selected.extend(bucket)
            continue
        # Trimmed by confidence rather than by position: a page of low-grade
        # guesses at the top of the answer would otherwise crowd out a
        # certain finding further down.
        bucket.sort(key=lambda i: i.confidence, reverse=True)
        selected.extend(bucket[:cap])
        truncated.append(category.value)

    return order_for_display(selected), suppressed, tuple(sorted(truncated))


__all__ = ["run_analyzers"]
