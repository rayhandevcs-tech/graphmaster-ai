"""The contract every grammar provider implements.

Modelled on ``app/ocr/base.py``, and for the same reasons. ``is_available``
answers a *configuration* question — is a checker reachable from this
deployment at all — and is probed at startup; ``check`` answers a
*per-submission* question and may fail at any time. Keeping them apart is what
lets a server with no grammar checker report "not installed here" while a
server whose checker has just fallen over reports a fault, and only one of
those is worth waking someone for.

Nothing in this module imports a grammar engine. A provider is chosen by the
factory and handed to the analyzer, so the analyzer never names an
implementation and every path through it can be exercised against a fake.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.models.enums import IssueSeverity


@dataclass(frozen=True, slots=True)
class GrammarMatch:
    """One finding, in provider-neutral terms.

    Deliberately *not* an :class:`~app.assessment.issues.AssessmentIssue`. A
    provider's job ends at "here is what I found, where, and how sure I am";
    turning that into an issue means choosing a category, a severity and
    wording addressed to a student, and those are the analyzer's decisions.
    A provider that built issues directly would have to know about
    ``IssueCategory`` — and a second provider would then be free to disagree
    with the first about what category grammar findings belong in.

    ``start`` and ``end`` are half-open indices into the text that was
    **submitted to the provider**, which is the normalised text. The analyzer
    maps them back to the student's original before building an issue.
    """

    #: Stable analytics slug, e.g. ``subject_verb_agreement``. Chosen from the
    #: provider's own rule metadata; never phrased for display.
    subtype: str
    severity: IssueSeverity
    #: What the provider objected to, as it appears in the checked text.
    original_text: str
    #: Addressed to the student. A rule identifier is not an explanation.
    explanation: str
    start: int
    end: int
    #: ``None`` where the provider offered no replacement, or offered several
    #: and none is clearly right. Inventing one is worse than offering none.
    suggested_text: str | None = None
    #: 0–1. Providers do not report confidence, so this is derived from how
    #: specific the finding is — see ``rules.py``.
    confidence: float = 0.8
    #: The rule that fired, for auditing a false positive back to its cause.
    rule_id: str = ""

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(
                f"Grammar match span [{self.start}, {self.end}) is not a valid half-open range."
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Grammar match confidence {self.confidence} is outside 0–1.")
        if not self.subtype:
            raise ValueError("A grammar match must carry a subtype; it is the analytics key.")


@dataclass(frozen=True, slots=True)
class GrammarReport:
    """What a provider returns from one check.

    ``latency_ms`` is on the report rather than measured by the caller because
    it is the *provider's* cost — the time on the wire and in the engine — and
    that is the number an operator needs when deciding whether a remote
    checker is worth its round trip. The analyzer's own cost is measured
    separately by the supervisor.
    """

    matches: tuple[GrammarMatch, ...] = ()
    provider: str = "none"
    latency_ms: float = 0.0
    #: Characters actually submitted, for the accuracy denominator's audit.
    checked_chars: int = 0


class GrammarUnavailableError(RuntimeError):
    """No checker is reachable — a deployment fact, not a fault.

    Raised when a provider is asked to check but is not configured, or its
    engine has never answered a health probe. The analyzer turns this into
    ``UNAVAILABLE``, which leaves the assessment ``complete``: a server without
    a grammar checker is not a server producing partial results.
    """


class GrammarCheckError(RuntimeError):
    """A configured checker failed this request — a fault.

    Timeouts, connection resets, malformed responses. The analyzer turns this
    into ``FAILED`` with the reason recorded, which is what distinguishes "the
    grammar checker crashed" from "this server has no grammar checker".

    The message is bound for operator logs and a teacher's screen, so it must
    never carry the endpoint, a credential, or the student's own text.
    """


@runtime_checkable
class GrammarProvider(Protocol):
    """One grammar engine, or the absence of one."""

    name: str

    def is_available(self) -> bool:
        """Whether this deployment has a checker to call.

        Cheap and cached. Called at startup to warm the decision and before
        each check to avoid a doomed round trip.
        """
        ...

    def check(self, text: str, *, language: str) -> GrammarReport:
        """Check ``text``.

        Raises :class:`GrammarUnavailableError` when there is nothing to call
        and :class:`GrammarCheckError` when the call failed. Returns an empty
        report when the text is clean — which is a different answer from
        either.
        """
        ...


__all__ = [
    "GrammarCheckError",
    "GrammarMatch",
    "GrammarProvider",
    "GrammarReport",
    "GrammarUnavailableError",
]
