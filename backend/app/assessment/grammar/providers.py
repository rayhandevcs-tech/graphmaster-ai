"""The three grammar providers.

``none`` is the default, and it is a real implementation rather than a null
check scattered through the analyzer: a deployment without a grammar checker
is the ordinary case, and it deserves an object that answers the same
questions as the other two.

``local`` and ``remote`` differ in three ways that matter and in nothing else:

* **Where the writing goes.** The local engine runs inside the deployment's
  own network; the remote one is a third party, and every answer checked
  against it leaves the institution. That is a decision for whoever deploys
  the platform, which is why it can only be made in configuration and why the
  default is neither.
* **What a failure means.** A localhost connection refused is a service that
  is not running. A remote timeout is the internet. Only the second is worth
  retrying, so only the second retries.
* **What is worth waiting for.** Both share one total budget, but the local
  engine has no excuse for using much of it.
"""

from __future__ import annotations

import time

from app.assessment.grammar.base import (
    GrammarProvider,
    GrammarReport,
    GrammarUnavailableError,
)
from app.assessment.grammar.languagetool import LanguageToolClient, Transport
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DisabledGrammarProvider:
    """No checker on this deployment.

    Not an error. ``is_available`` answers ``False`` and ``check`` raises
    :class:`GrammarUnavailableError`, which the analyzer reports as
    ``unavailable`` — leaving the assessment *complete*, because a server
    without a grammar checker is not a server producing partial results.
    """

    name = "none"

    def is_available(self) -> bool:
        return False

    def check(self, text: str, *, language: str) -> GrammarReport:
        raise GrammarUnavailableError("No grammar provider is configured on this server.")


class LanguageToolProvider:
    """Shared behaviour for the two LanguageTool deployments.

    The health probe is cached with a short time to live, and that detail is
    load-bearing. Caching a *positive* answer forever would be fine; caching a
    negative one would not — a platform that starts before its LanguageTool
    container is ready would then report grammar unavailable until someone
    restarted it, which is precisely the graceless startup failure this is
    meant to avoid. So a negative answer expires and is re-probed, while the
    request path still never pays for a doomed round trip more than once per
    interval.
    """

    name = "languagetool"
    #: Attempts beyond the first. Overridden per deployment below.
    retries = 0

    def __init__(
        self,
        settings: Settings,
        *,
        endpoint: str,
        transport: Transport | None = None,
    ) -> None:
        self.settings = settings
        self.max_chars = settings.GRAMMAR_MAX_CHARS
        self.health_ttl = settings.GRAMMAR_HEALTH_TTL_SECONDS
        self._client = LanguageToolClient(
            endpoint,
            timeout=settings.GRAMMAR_TIMEOUT_SECONDS,
            retries=self.retries,
            transport=transport,
        )
        self._healthy: bool | None = None
        self._checked_at = 0.0

    # ── Availability ─────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        if self._healthy and not self._expired():
            return True
        if self._healthy is False and not self._expired():
            return False

        self._healthy = self._client.probe()
        self._checked_at = time.monotonic()
        if not self._healthy:
            logger.warning(
                "The %s grammar engine did not answer a health probe; grammar analysis is "
                "unavailable until it does.",
                self.name,
            )
        return self._healthy

    def _expired(self) -> bool:
        return (time.monotonic() - self._checked_at) >= self.health_ttl

    # ── Checking ─────────────────────────────────────────────────────────────

    def check(self, text: str, *, language: str) -> GrammarReport:
        if not text.strip():
            # Nothing to check is not a failure, and posting an empty body to
            # a checker to be told so would spend a round trip learning it.
            return GrammarReport(provider=self.name)

        if not self.is_available():
            raise GrammarUnavailableError(
                f"The {self.name} grammar engine is not answering on this server."
            )

        # Validated here rather than at the far end: a checker's own limit is
        # enforced with a 4xx that costs the round trip, and the public service
        # enforces it by truncating — which would report offsets into a
        # different string from the one the student wrote.
        checked = text[: self.max_chars]
        if len(checked) < len(text):
            logger.info(
                "Answer of %d characters truncated to %d for grammar analysis.",
                len(text),
                self.max_chars,
            )

        report = self._client.check(checked, language=language)
        # Stamped here so an issue can be audited back to the deployment that
        # produced it, not just to the engine family.
        return GrammarReport(
            matches=report.matches,
            provider=self.name,
            latency_ms=report.latency_ms,
            checked_chars=report.checked_chars,
        )


class LocalLanguageToolProvider(LanguageToolProvider):
    """A LanguageTool server inside the deployment's own network.

    No retries. A refused connection to a host the deployment operates is a
    service that is down, and a second immediate attempt will find it down
    too — the budget is better returned to the request.
    """

    name = "local"
    retries = 0

    def __init__(self, settings: Settings, *, transport: Transport | None = None) -> None:
        endpoint = (
            settings.GRAMMAR_API_URL or f"http://{settings.GRAMMAR_HOST}:{settings.GRAMMAR_PORT}"
        )
        super().__init__(settings, endpoint=endpoint, transport=transport)


class RemoteLanguageToolProvider(LanguageToolProvider):
    """A hosted LanguageTool service.

    Retries, because the failures between here and a third party are the
    transient kind. Within the same total budget: the configured timeout is
    the worst case however many attempts happen inside it, because this call
    sits in the request that is scoring a student's work.

    Every answer checked here leaves the institution. See
    ``docs/architecture/10-assessment-architecture.md`` §12 — that is a
    deployment decision with a privacy consequence, and it is why nothing
    about the student travels with the text.
    """

    name = "remote"

    def __init__(self, settings: Settings, *, transport: Transport | None = None) -> None:
        self.retries = settings.GRAMMAR_MAX_RETRIES
        if not settings.GRAMMAR_API_URL:
            raise ValueError("GRAMMAR_PROVIDER is 'remote' but GRAMMAR_API_URL is not set.")
        super().__init__(settings, endpoint=settings.GRAMMAR_API_URL, transport=transport)


__all__ = [
    "DisabledGrammarProvider",
    "GrammarProvider",
    "LanguageToolProvider",
    "LocalLanguageToolProvider",
    "RemoteLanguageToolProvider",
]
