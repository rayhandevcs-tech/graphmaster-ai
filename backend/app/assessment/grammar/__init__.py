"""Grammar providers: the assessment engine's only outbound dependency.

Every other analyzer is a pure function of the parsed document. This one is
not — it talks to an engine that may be on another host, may be a third party,
and may be down. The provider abstraction exists so that fact is contained in
one place: the analyzer above it sees a small synchronous interface that
either returns findings, says it has no engine, or says the call failed.
"""

from __future__ import annotations

from app.assessment.grammar.base import (
    GrammarCheckError,
    GrammarMatch,
    GrammarProvider,
    GrammarReport,
    GrammarUnavailableError,
)
from app.assessment.grammar.factory import build_grammar_provider
from app.assessment.grammar.providers import (
    DisabledGrammarProvider,
    LocalLanguageToolProvider,
    RemoteLanguageToolProvider,
)

__all__ = [
    "DisabledGrammarProvider",
    "GrammarCheckError",
    "GrammarMatch",
    "GrammarProvider",
    "GrammarReport",
    "GrammarUnavailableError",
    "LocalLanguageToolProvider",
    "RemoteLanguageToolProvider",
    "build_grammar_provider",
]
