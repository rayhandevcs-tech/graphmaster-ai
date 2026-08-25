"""Choosing the provider.

The one place in the codebase that names a concrete grammar implementation.
The analyzer receives whatever this returns, so it can be exercised against a
fake without a network, a JVM or a container — and so no analyzer has to be
edited to add a third engine.

A misconfiguration here degrades to ``none`` rather than raising. The rule is
the one a malformed achievement rule already follows: a typo in a deployment's
environment must not cost a student the submission that happened to hit it.
"""

from __future__ import annotations

from app.assessment.grammar.base import GrammarProvider
from app.assessment.grammar.providers import (
    DisabledGrammarProvider,
    LocalLanguageToolProvider,
    RemoteLanguageToolProvider,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

BUILDERS = {
    "none": lambda settings: DisabledGrammarProvider(),
    "local": LocalLanguageToolProvider,
    "remote": RemoteLanguageToolProvider,
}


def build_grammar_provider(settings: Settings | None = None) -> GrammarProvider:
    """The configured provider, or the disabled one if it cannot be built."""
    settings = settings or get_settings()
    name = settings.GRAMMAR_PROVIDER

    builder = BUILDERS.get(name)
    if builder is None:  # pragma: no cover - the Literal type forbids it
        logger.warning("Unknown GRAMMAR_PROVIDER %r; grammar analysis is disabled.", name)
        return DisabledGrammarProvider()

    try:
        return builder(settings)
    except Exception as exc:
        # A bad endpoint, a remote provider with no URL. Logged loudly,
        # because this is an operator's mistake and they need to see it — and
        # then treated as "no checker here", which is a state the whole
        # pipeline already handles.
        logger.error(
            "Could not build the %r grammar provider (%s); grammar analysis is disabled. %s",
            name,
            type(exc).__name__,
            exc,
        )
        return DisabledGrammarProvider()


__all__ = ["BUILDERS", "build_grammar_provider"]
