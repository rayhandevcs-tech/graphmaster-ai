"""The shared spaCy pipeline.

Loaded once per process. The model is tens of megabytes and takes on the order
of a second to read from disk, so constructing it per request would dominate
the 2-second analysis budget of NFR-1.2.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.core.exceptions import AnalysisEngineUnavailableError
from app.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from spacy.language import Language

logger = get_logger(__name__)

#: Components switched off at load time.
#:
#: ``ner`` is the most expensive stage in the default pipeline and nothing here
#: uses entity labels — a graph description's dates and quantities are scored
#: as ordinary tokens. ``tagger``, ``attribute_ruler`` and ``lemmatizer`` are
#: required for lemma matching, and ``parser`` for both sentence segmentation
#: and the subordinate-clause ratio, so none of those can be disabled.
DISABLED_COMPONENTS = ("ner",)


@lru_cache
def get_nlp() -> Language:
    """The process-wide pipeline.

    Raises :class:`AnalysisEngineUnavailableError` when the language model is
    not installed, rather than the bare ``OSError`` spaCy raises, so the
    operator sees the command that fixes it instead of a stack trace ending in
    a path they have never heard of.
    """
    settings = get_settings()

    try:
        import spacy
    except ImportError as exc:  # pragma: no cover - spaCy is a hard dependency
        raise AnalysisEngineUnavailableError(
            "spaCy is not installed. Run: pip install -e '.[dev]'"
        ) from exc

    try:
        nlp = spacy.load(settings.SPACY_MODEL, disable=list(DISABLED_COMPONENTS))
    except OSError as exc:
        raise AnalysisEngineUnavailableError(
            f"The spaCy model {settings.SPACY_MODEL!r} is not installed. "
            f"Run: python -m spacy download {settings.SPACY_MODEL}"
        ) from exc

    logger.info(
        "Loaded spaCy model %s (pipes: %s)", settings.SPACY_MODEL, ", ".join(nlp.pipe_names)
    )
    return nlp


def is_available() -> bool:
    """Whether analysis can run at all on this server.

    Answered by attempting the load, because the only reliable test of whether
    a model is installed is loading it — and the result is cached, so a
    successful probe is also the warm-up.
    """
    try:
        get_nlp()
    except AnalysisEngineUnavailableError:
        return False
    return True


def warm_up() -> bool:
    """Load the model and run one throwaway parse during boot.

    The first parse of a process is measurably slower than the rest: spaCy
    defers some of the model's initialisation until it is first used. Without
    this, that cost lands on whichever student happens to submit first.

    Returns whether the engine is usable; never raises, so a server with no
    model still starts and serves everything that is not scoring.
    """
    try:
        nlp = get_nlp()
    except AnalysisEngineUnavailableError as exc:
        logger.warning("Analysis engine unavailable: %s", exc.message)
        return False

    try:
        nlp("Sales rose sharply before levelling off.")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("spaCy warm-up parse failed: %s", exc)
        return False

    return True


def pipeline_info() -> dict[str, Any]:
    """Model name, version and active pipes, for the health and engine endpoints."""
    settings = get_settings()
    info: dict[str, Any] = {
        "model": settings.SPACY_MODEL,
        "available": False,
        "version": None,
        "pipes": [],
    }
    try:
        nlp = get_nlp()
    except AnalysisEngineUnavailableError:
        return info

    info["available"] = True
    info["version"] = nlp.meta.get("version")
    info["pipes"] = list(nlp.pipe_names)
    return info
