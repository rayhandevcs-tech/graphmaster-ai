"""Which analyzers this deployment runs.

Configuration names them, in order, exactly as ``OCR_PROVIDER_ORDER`` names
the recognition chain. An unknown name is logged and skipped rather than
raising: the same rule that makes a malformed achievement rule inert applies
here, because a typo in a deployment's environment must not cost a student the
submission that happened to hit it.
"""

from __future__ import annotations

from collections.abc import Callable

from app.assessment.analyzers import (
    GraphAccuracyAnalyzer,
    SentenceAnalyzer,
    SpellingAnalyzer,
    VocabularyAnalyzer,
    WordUsageAnalyzer,
    WritingAnalyzer,
)
from app.assessment.protocol import Analyzer
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Every analyzer this build knows how to construct.
#:
#: Factories taking the deployment's settings, rather than instances: an
#: analyzer may hold a provider, a client or a loaded word list, and building
#: it belongs to whoever assembles the pipeline rather than to import time.
BUILDERS: dict[str, Callable[[Settings], Analyzer]] = {
    "vocabulary": VocabularyAnalyzer,
    "writing": WritingAnalyzer,
    "spelling": SpellingAnalyzer,
    "sentence": SentenceAnalyzer,
    "word_usage": WordUsageAnalyzer,
    "graph_accuracy": GraphAccuracyAnalyzer,
}


def build_analyzers(settings: Settings | None = None) -> list[Analyzer]:
    """The configured analyzers, in configured order."""
    settings = settings or get_settings()

    if not settings.ASSESSMENT_ENABLED:
        return []

    analyzers: list[Analyzer] = []
    for name in settings.assessment_analyzers:
        builder = BUILDERS.get(name)
        if builder is None:
            logger.warning(
                "Unknown analyzer %r in ASSESSMENT_ANALYZERS; skipping. Known: %s",
                name,
                ", ".join(sorted(BUILDERS)),
            )
            continue
        analyzers.append(builder(settings))

    return analyzers


def warm_up(settings: Settings | None = None) -> None:
    """Load whatever the configured analyzers need, during boot.

    Failures are logged and swallowed: a warm-up is an optimisation, and an
    analyzer that cannot preload is still able to report itself unavailable on
    the first request rather than stopping the server from starting.
    """
    for analyzer in build_analyzers(settings):
        preload = getattr(analyzer, "warm_up", None)
        if preload is None:
            continue
        try:
            preload()
        except Exception as exc:
            logger.warning("Could not warm up analyzer %s: %s", analyzer.name, exc)


def known_analyzers() -> list[str]:
    """Every analyzer name this build supports, for the engine-status endpoint."""
    return sorted(BUILDERS)


__all__ = ["BUILDERS", "build_analyzers", "known_analyzers", "warm_up"]
