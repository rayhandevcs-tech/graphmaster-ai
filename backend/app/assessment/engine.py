"""The assessment entry point.

One function, called from :func:`app.nlp.analyzer.analyse` once the parse and
the existing engine's work are done. It builds the context, runs the
configured analyzers, and returns the result — or ``None`` if assessment is
switched off for this deployment.

It cannot raise. The supervisor already contains every analyzer's failures,
and this adds the outer belt: building the context, or building the analyzer
list from a malformed configuration, must not be able to fail an analysis that
would otherwise have scored perfectly well.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from app.assessment.protocol import AssessmentContext
from app.assessment.registry import build_analyzers
from app.assessment.result import AssessmentResult
from app.assessment.supervisor import run_analyzers
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.enums import GraphType
from app.nlp.detector import DetectionResult
from app.nlp.normalise import NormalisedText
from app.nlp.terms import CompiledTargets
from app.nlp.writing import WritingQuality

if TYPE_CHECKING:  # pragma: no cover
    from spacy.tokens import Doc

logger = get_logger(__name__)


def run_assessment(
    *,
    text: str,
    doc: Doc,
    normalised: NormalisedText,
    targets: CompiledTargets,
    detection: DetectionResult,
    writing: WritingQuality,
    chart_data: Mapping[str, Any] | None = None,
    graph_type: GraphType | None = None,
    settings: Settings | None = None,
) -> AssessmentResult | None:
    """Run the diagnostic pass. Returns ``None`` when it is disabled."""
    settings = settings or get_settings()

    if not settings.ASSESSMENT_ENABLED:
        return None

    try:
        analyzers = build_analyzers(settings)
        if not analyzers:
            return None

        ctx = AssessmentContext(
            text=text,
            doc=doc,
            normalised=normalised,
            targets=targets,
            detection=detection,
            writing=writing,
            chart_data=chart_data,
            graph_type=graph_type,
        )
        return run_analyzers(analyzers, ctx, settings=settings)
    except Exception as exc:
        # A student's submission is not lost because the diagnostic pass could
        # not be assembled. The score has already been computed by the time
        # this runs, and returning None simply means the result carries no
        # assessment — the same shape a submission scored before this feature
        # existed has.
        logger.exception("Assessment could not be assembled: %s", exc)
        return None


__all__ = ["run_assessment"]
