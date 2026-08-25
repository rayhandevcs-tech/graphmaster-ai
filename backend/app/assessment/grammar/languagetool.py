"""The LanguageTool HTTP client, shared by the local and remote providers.

Local and remote LanguageTool speak the *same* protocol — ``POST /v2/check``
with a form body, a JSON document back. They differ in where the engine runs,
what a failure means, and what leaves the building; they do not differ in
wire format, so there is one client and two providers configured around it.

Three things here are worth reading before changing anything:

**The timeout is a total budget, not a per-attempt one.** A three-second
timeout with one retry would otherwise permit six seconds of waiting, and this
call happens inside the request that is scoring a student's submission. Every
attempt is given whatever is left of the original budget, so the configured
number is the worst case however many attempts are made.

**Only transient failures are retried.** A 4xx means the request itself is
wrong — the wrong endpoint, a body the server rejects, a rate limit that a
second immediate attempt would also hit. Retrying it wastes the budget and
delays the honest failure.

**Offsets arrive in UTF-16 code units.** LanguageTool is a Java service, and
Java counts a string in UTF-16. For ordinary prose that is identical to
Python's character indexing, but one emoji in the answer shifts every
subsequent offset by one and every highlight after it lands on the wrong
words. The conversion is built only when the text actually contains a
character outside the basic plane, so the common case pays nothing.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from app.assessment.grammar.base import GrammarCheckError, GrammarMatch, GrammarReport
from app.assessment.grammar.rules import classify, confidence_for
from app.core.logging import get_logger

logger = get_logger(__name__)

#: A transport: ``(url, body_or_None, timeout_seconds) -> (status, body_bytes)``.
#:
#: Injected so every path through this client — a timeout, a 500, a truncated
#: JSON document — is exercised by a test rather than reasoned about. The
#: default is the standard library; nothing here needs an HTTP dependency.
Transport = Callable[[str, bytes | None, float], tuple[int, bytes]]

#: The paths LanguageTool serves. Appended to a base URL, or recognised on one
#: that already carries them — an operator who pastes the URL from
#: LanguageTool's own documentation has pasted the full path.
CHECK_PATH = "/v2/check"
LANGUAGES_PATH = "/v2/languages"

#: Below this there is no point starting an attempt: a request given 20ms will
#: time out having achieved nothing but the loss of the remaining budget.
MIN_ATTEMPT_SECONDS = 0.05

#: HTTP statuses worth a second attempt. 429 is deliberately absent: a rate
#: limit that has just refused us will refuse us again a moment later, and the
#: budget is better spent failing honestly.
RETRYABLE_STATUSES = frozenset({500, 502, 503, 504})

#: Response bytes above which the document is refused unread.
#:
#: A checker returning a hundred megabytes is a checker that is not
#: LanguageTool, and parsing it to find that out would be the actual damage.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _urlopen(url: str, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    """The default transport: the standard library, with a socket timeout."""
    # The scheme is validated by `normalise_endpoint` before any URL reaches
    # here, so this cannot be pointed at a file:// or a gopher:// target.
    request = urllib.request.Request(
        url,
        data=body,
        method="POST" if body is not None else "GET",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            # Named so an operator reading their LanguageTool access log can
            # tell which service is calling. Carries no user identity.
            "User-Agent": "GraphMaster/1.0 (+assessment)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return int(response.status), response.read(MAX_RESPONSE_BYTES + 1)


def normalise_endpoint(url: str) -> str:
    """Validate a configured URL and reduce it to a base.

    Refuses anything that is not HTTP, because this value comes from a
    deployment's environment and a client that will open ``file://`` on
    request is a file-disclosure primitive one typo away from being used.
    """
    cleaned = url.strip().rstrip("/")
    if not cleaned:
        raise ValueError("The grammar endpoint is empty.")

    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            f"The grammar endpoint must be http or https, not {parsed.scheme or 'a bare host'!r}."
        )
    if not parsed.netloc:
        raise ValueError("The grammar endpoint has no host.")

    for path in (CHECK_PATH, LANGUAGES_PATH):
        if cleaned.endswith(path):
            return cleaned[: -len(path)]
    return cleaned


class LanguageToolClient:
    """One configured LanguageTool endpoint."""

    def __init__(
        self,
        endpoint: str,
        *,
        timeout: float,
        retries: int = 0,
        transport: Transport | None = None,
    ) -> None:
        self.base = normalise_endpoint(endpoint)
        self.timeout = timeout
        self.retries = max(0, retries)
        self._transport = transport or _urlopen

    # ── Requests ─────────────────────────────────────────────────────────────

    def probe(self) -> bool:
        """Whether the endpoint answers. One attempt, no retries.

        A health check that retries is a health check that takes the timeout
        several times over during a startup where the answer is already known.
        """
        try:
            status, _ = self._transport(self.base + LANGUAGES_PATH, None, self.timeout)
        except Exception as exc:
            logger.info("Grammar endpoint did not answer a health probe: %s", type(exc).__name__)
            return False
        return 200 <= status < 300

    def check(self, text: str, *, language: str) -> GrammarReport:
        """Check ``text`` and map the response onto :class:`GrammarMatch`."""
        body = urllib.parse.urlencode(
            {
                "text": text,
                "language": language,
                # Off: LanguageTool's "picky" level adds the style rules this
                # analyzer deliberately does not report, so asking for them
                # would spend the round trip on findings that are discarded.
                "level": "default",
            }
        ).encode("utf-8")

        started = time.perf_counter()
        payload = self._request(self.base + CHECK_PATH, body)
        latency = (time.perf_counter() - started) * 1000

        return GrammarReport(
            matches=tuple(parse_matches(payload, text)),
            latency_ms=round(latency, 3),
            checked_chars=len(text),
        )

    def _request(self, url: str, body: bytes) -> dict[str, Any]:
        """One request, retried within a single shared deadline."""
        deadline = time.monotonic() + self.timeout
        last: Exception | None = None

        for attempt in range(self.retries + 1):
            remaining = deadline - time.monotonic()
            if remaining < MIN_ATTEMPT_SECONDS:
                break

            try:
                status, raw = self._transport(url, body, remaining)
            except urllib.error.HTTPError as exc:
                status = int(exc.code)
                if status not in RETRYABLE_STATUSES:
                    raise GrammarCheckError(f"The grammar service returned HTTP {status}.") from exc
                last = exc
                continue
            except Exception as exc:
                # Timeouts, connection resets, DNS failures. Transient by
                # nature, so worth the remaining budget — but never the
                # student's submission.
                last = exc
                logger.info(
                    "Grammar request attempt %d failed: %s", attempt + 1, type(exc).__name__
                )
                continue

            if status in RETRYABLE_STATUSES:
                last = GrammarCheckError(f"The grammar service returned HTTP {status}.")
                continue
            if not 200 <= status < 300:
                raise GrammarCheckError(f"The grammar service returned HTTP {status}.")

            return _decode(raw)

        # The message names the failure type, never the endpoint: this string
        # reaches operator logs and a teacher's screen, and a hostname there is
        # an internal detail leaking towards a classroom.
        reason = type(last).__name__ if last is not None else "no time left in the budget"
        raise GrammarCheckError(f"The grammar service could not be reached ({reason}).")


def _decode(raw: bytes) -> dict[str, Any]:
    """Parse a response body, refusing one that is too large or not JSON."""
    if len(raw) > MAX_RESPONSE_BYTES:
        raise GrammarCheckError("The grammar service returned an implausibly large response.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GrammarCheckError(
            "The grammar service returned a response that is not JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise GrammarCheckError("The grammar service returned a response of the wrong shape.")
    return payload


# ── Response mapping ─────────────────────────────────────────────────────────


def parse_matches(payload: dict[str, Any], text: str) -> list[GrammarMatch]:
    """Every usable match in a ``/v2/check`` response.

    Individually defensive: one malformed match is skipped, not allowed to
    discard the rest. A response whose shape drifted in a LanguageTool upgrade
    should cost the findings it broke, and nothing else.
    """
    raw_matches = payload.get("matches")
    if not isinstance(raw_matches, list):
        return []

    to_python = _offset_converter(text)
    matches: list[GrammarMatch] = []
    for raw in raw_matches:
        if not isinstance(raw, dict):
            continue
        match = _match_from(raw, text, to_python)
        if match is not None:
            matches.append(match)
    return matches


def _match_from(
    raw: dict[str, Any], text: str, to_python: Callable[[int], int]
) -> GrammarMatch | None:
    """One match, or ``None`` if it is unusable or belongs to another analyzer."""
    rule = raw.get("rule")
    classification = classify(rule if isinstance(rule, dict) else {})
    if classification is None:
        return None

    try:
        start = to_python(int(raw["offset"]))
        end = to_python(int(raw["offset"]) + int(raw["length"]))
    except (KeyError, TypeError, ValueError):
        return None

    # A span outside the text is a mapping that has gone wrong somewhere, and
    # a highlight built from it would land on the wrong words — or on none.
    # Dropped rather than clamped: a clamped span is a confident-looking
    # highlight of an arbitrary region.
    if not 0 <= start < end <= len(text):
        return None

    replacements = [
        str(r["value"])
        for r in (raw.get("replacements") or [])
        if isinstance(r, dict) and isinstance(r.get("value"), str)
    ]
    suggestion = replacements[0] if len(replacements) == 1 else None

    return GrammarMatch(
        subtype=classification.subtype,
        severity=classification.severity,
        original_text=text[start:end],
        explanation=_explanation(raw),
        start=start,
        end=end,
        suggested_text=suggestion,
        confidence=confidence_for(classification, len(replacements)),
        rule_id=str((rule or {}).get("id") or "")[:64] if isinstance(rule, dict) else "",
    )


def _explanation(raw: dict[str, Any]) -> str:
    """The wording shown to the student.

    ``message`` in preference to ``shortMessage``: the short form is a label
    ("Grammar"), and a label is not an explanation. Falls back through both to
    a plain sentence, because an issue with an empty explanation is one the
    student cannot act on.
    """
    for key in ("message", "shortMessage"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "This does not read as standard English."


def _offset_converter(text: str) -> Callable[[int], int]:
    """Map UTF-16 code-unit offsets onto Python string indices.

    Built only when the text contains a character outside the basic plane —
    an emoji, most often. Without one, the two indexings are identical and the
    identity function is both correct and free.
    """
    if all(ord(ch) <= 0xFFFF for ch in text):
        return lambda offset: offset

    # Prefix table: for each UTF-16 offset, the Python index it lands on.
    # Built once per check rather than per match; an answer is a few thousand
    # characters, so this is a small list and a single pass.
    python_index: list[int] = []
    for index, ch in enumerate(text):
        python_index.append(index)
        if ord(ch) > 0xFFFF:
            # The low surrogate maps to the same character: a span that starts
            # mid-pair is malformed, and pointing it at the pair's character
            # is the only non-arbitrary answer.
            python_index.append(index)
    python_index.append(len(text))

    def convert(offset: int) -> int:
        if offset < 0 or offset >= len(python_index):
            raise ValueError(f"UTF-16 offset {offset} is outside the checked text.")
        return python_index[offset]

    return convert


__all__ = ["LanguageToolClient", "Transport", "normalise_endpoint", "parse_matches"]
