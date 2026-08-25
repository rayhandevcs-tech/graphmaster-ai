"""The grammar provider abstraction, without a network.

Every path here is driven through an injected transport rather than a real
LanguageTool, which is the point of the abstraction: a timeout, a 502, a
truncated JSON document and an engine that is simply not there are all things
that happen in production and none of them should need a container to
reproduce.

The recurring theme is what the providers *refuse* to do — retry a 4xx, spend
more than the configured budget, report a misspelling, or name their endpoint
in a message that will reach a classroom.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.assessment.grammar.base import (
    GrammarCheckError,
    GrammarMatch,
    GrammarProvider,
    GrammarUnavailableError,
)
from app.assessment.grammar.factory import build_grammar_provider
from app.assessment.grammar.languagetool import (
    LanguageToolClient,
    normalise_endpoint,
    parse_matches,
)
from app.assessment.grammar.providers import (
    DisabledGrammarProvider,
    LocalLanguageToolProvider,
    RemoteLanguageToolProvider,
)
from app.assessment.grammar.rules import classify, confidence_for
from app.core.config import get_settings
from app.models.enums import IssueSeverity


def settings(**overrides):
    return get_settings().model_copy(update=overrides)


def rule(rule_id: str, issue_type: str = "grammar", category: str = "GRAMMAR") -> dict:
    return {"id": rule_id, "issueType": issue_type, "category": {"id": category}}


def match(
    offset: int, length: int, *, rule_id="SUBJECT_VERB_AGREEMENT", replacements=("fixed",), **kw
):
    return {
        "message": kw.get("message", "That does not agree."),
        "offset": offset,
        "length": length,
        "replacements": [{"value": v} for v in replacements],
        "rule": kw.get("rule", rule(rule_id)),
    }


def responder(payload, *, status=200, languages_status=200):
    """A transport that answers the health probe and returns ``payload``."""

    def transport(url, body, timeout):
        if url.endswith("/v2/languages"):
            return languages_status, b'[{"name":"English"}]'
        return status, json.dumps(payload).encode("utf-8")

    return transport


# ── The contract ─────────────────────────────────────────────────────────────


class TestProtocol:
    def test_all_three_providers_satisfy_the_protocol(self):
        built = [
            DisabledGrammarProvider(),
            LocalLanguageToolProvider(settings(), transport=responder({"matches": []})),
            RemoteLanguageToolProvider(
                settings(GRAMMAR_API_URL="https://example.test"),
                transport=responder({"matches": []}),
            ),
        ]

        assert all(isinstance(p, GrammarProvider) for p in built)
        assert [p.name for p in built] == ["none", "local", "remote"]

    def test_a_match_refuses_an_inverted_span(self):
        with pytest.raises(ValueError, match="half-open"):
            GrammarMatch(
                subtype="punctuation",
                severity=IssueSeverity.LOW,
                original_text="x",
                explanation="…",
                start=9,
                end=4,
            )

    def test_a_match_refuses_an_empty_subtype(self):
        # The subtype is the analytics key: an issue without one cannot be
        # grouped, and a year of class reports is grouped by it.
        with pytest.raises(ValueError, match="subtype"):
            GrammarMatch(
                subtype="",
                severity=IssueSeverity.LOW,
                original_text="x",
                explanation="…",
                start=0,
                end=1,
            )


# ── The disabled provider ────────────────────────────────────────────────────


class TestDisabled:
    def test_it_is_never_available(self):
        assert DisabledGrammarProvider().is_available() is False

    def test_checking_raises_unavailable_not_an_error(self):
        # Unavailable, not failed. The difference decides whether every
        # submission on a server with no grammar engine is marked partial.
        with pytest.raises(GrammarUnavailableError):
            DisabledGrammarProvider().check("Sales go up.", language="en-GB")

    def test_it_is_what_the_default_configuration_builds(self):
        assert isinstance(build_grammar_provider(settings()), DisabledGrammarProvider)


# ── Endpoint handling ────────────────────────────────────────────────────────


class TestEndpoints:
    def test_a_base_url_gains_the_check_path(self):
        client = LanguageToolClient("http://lt.internal:8081", timeout=1.0)
        assert client.base == "http://lt.internal:8081"

    @pytest.mark.parametrize(
        "given",
        [
            "https://api.example.test/v2/check",
            "https://api.example.test/v2/languages",
            "https://api.example.test/",
        ],
    )
    def test_a_full_path_is_recognised_rather_than_doubled(self, given: str):
        # An operator who pastes the URL from LanguageTool's own documentation
        # has pasted the full path, and /v2/check/v2/check is a 404.
        assert LanguageToolClient(given, timeout=1.0).base == "https://api.example.test"

    @pytest.mark.parametrize("given", ["file:///etc/passwd", "gopher://x", "lt.internal:8081", ""])
    def test_a_non_http_endpoint_is_refused(self, given: str):
        # This value comes from a deployment's environment. A client that will
        # open file:// on request is a disclosure primitive one typo away.
        with pytest.raises(ValueError):
            normalise_endpoint(given)

    def test_the_local_provider_builds_its_url_from_host_and_port(self):
        provider = LocalLanguageToolProvider(
            settings(GRAMMAR_HOST="lt", GRAMMAR_PORT=9999, GRAMMAR_API_URL=None),
            transport=responder({"matches": []}),
        )
        assert provider._client.base == "http://lt:9999"

    def test_an_explicit_url_overrides_host_and_port_for_the_local_provider(self):
        # A local engine behind a path prefix or a proxy is still local.
        provider = LocalLanguageToolProvider(
            settings(GRAMMAR_HOST="lt", GRAMMAR_PORT=9999, GRAMMAR_API_URL="http://proxy/lt"),
            transport=responder({"matches": []}),
        )
        assert provider._client.base == "http://proxy/lt"

    def test_a_remote_provider_without_a_url_refuses_to_be_built(self):
        with pytest.raises(ValueError, match="GRAMMAR_API_URL"):
            RemoteLanguageToolProvider(settings(GRAMMAR_API_URL=None))

    def test_the_factory_degrades_to_disabled_rather_than_raising(self):
        # A typo in a deployment's environment must not cost a student the
        # submission that happened to hit it.
        broken = settings(GRAMMAR_PROVIDER="remote", GRAMMAR_API_URL=None)

        assert isinstance(build_grammar_provider(broken), DisabledGrammarProvider)


# ── Health probes ────────────────────────────────────────────────────────────


class TestAvailability:
    def test_an_engine_that_answers_is_available(self):
        provider = LocalLanguageToolProvider(settings(), transport=responder({"matches": []}))
        assert provider.is_available() is True

    def test_an_engine_that_does_not_answer_is_unavailable(self):
        def dead(url, body, timeout):
            raise ConnectionRefusedError("nothing is listening")

        provider = LocalLanguageToolProvider(settings(), transport=dead)

        assert provider.is_available() is False
        with pytest.raises(GrammarUnavailableError):
            provider.check("Sales go up.", language="en-GB")

    def test_a_probe_that_answers_with_an_error_status_is_unavailable(self):
        provider = LocalLanguageToolProvider(
            settings(), transport=responder({"matches": []}, languages_status=503)
        )
        assert provider.is_available() is False

    def test_a_positive_probe_is_cached_within_its_lifetime(self):
        calls = []

        def counting(url, body, timeout):
            calls.append(url)
            return 200, b"[]"

        provider = LocalLanguageToolProvider(
            settings(GRAMMAR_HEALTH_TTL_SECONDS=60.0), transport=counting
        )
        provider.is_available()
        provider.is_available()
        provider.is_available()

        assert len(calls) == 1

    def test_a_negative_probe_expires_and_is_re_probed(self):
        """The graceless startup failure this is here to prevent.

        A platform that starts before its LanguageTool container is ready must
        find it on the next submission, not stay broken until someone
        restarts it.
        """
        state = {"up": False}

        def flaky(url, body, timeout):
            if not state["up"]:
                raise ConnectionRefusedError("not yet")
            return 200, b"[]"

        provider = LocalLanguageToolProvider(
            settings(GRAMMAR_HEALTH_TTL_SECONDS=60.0), transport=flaky
        )
        assert provider.is_available() is False

        state["up"] = True
        provider._checked_at -= 61.0  # the interval has passed

        assert provider.is_available() is True


# ── Failure handling ─────────────────────────────────────────────────────────


class TestFailures:
    def _provider(self, transport, **overrides):
        provider = LocalLanguageToolProvider(settings(**overrides), transport=transport)
        provider._healthy, provider._checked_at = True, float("inf")
        return provider

    def test_a_timeout_becomes_a_check_error_not_an_exception_from_the_socket(self):
        def slow(url, body, timeout):
            raise TimeoutError("timed out")

        with pytest.raises(GrammarCheckError):
            self._provider(slow).check("Sales go up.", language="en-GB")

    def test_a_client_error_is_not_retried(self):
        attempts = []

        def bad_request(url, body, timeout):
            attempts.append(url)
            raise urllib.error.HTTPError(url, 400, "Bad Request", {}, None)

        with pytest.raises(GrammarCheckError, match="400"):
            self._provider(bad_request, GRAMMAR_MAX_RETRIES=3).check("x y z", language="en-GB")

        # Once. A 400 means the request itself is wrong, and repeating it
        # spends the budget to be told so again.
        assert len(attempts) == 1

    def test_a_server_error_is_retried_by_the_remote_provider(self):
        attempts = []

        def flaky(url, body, timeout):
            if url.endswith("/v2/languages"):
                return 200, b"[]"
            attempts.append(url)
            if len(attempts) == 1:
                return 503, b"unavailable"
            return 200, json.dumps({"matches": []}).encode()

        provider = RemoteLanguageToolProvider(
            settings(GRAMMAR_API_URL="https://example.test", GRAMMAR_MAX_RETRIES=1),
            transport=flaky,
        )
        report = provider.check("Sales go up over the period.", language="en-GB")

        assert len(attempts) == 2
        assert report.matches == ()

    def test_the_local_provider_does_not_retry(self):
        attempts = []

        def failing(url, body, timeout):
            if url.endswith("/v2/languages"):
                return 200, b"[]"
            attempts.append(url)
            return 503, b"down"

        provider = LocalLanguageToolProvider(settings(GRAMMAR_MAX_RETRIES=3), transport=failing)
        with pytest.raises(GrammarCheckError):
            provider.check("Sales go up.", language="en-GB")

        # A refused connection to a host the deployment operates is a service
        # that is down, and it will be down a millisecond later too.
        assert len(attempts) == 1

    def test_retries_share_one_budget_rather_than_multiplying_it(self):
        """The timeout is the worst case, whatever the retry count says.

        This call sits inside the request that is scoring a submission. A
        per-attempt timeout would let two retries turn a three-second budget
        into nine seconds of a student waiting.
        """
        given = []

        def slow(url, body, timeout):
            if url.endswith("/v2/languages"):
                return 200, b"[]"
            given.append(timeout)
            raise TimeoutError("timed out")

        provider = RemoteLanguageToolProvider(
            settings(
                GRAMMAR_API_URL="https://example.test",
                GRAMMAR_MAX_RETRIES=3,
                GRAMMAR_TIMEOUT_SECONDS=1.0,
            ),
            transport=slow,
        )
        with pytest.raises(GrammarCheckError):
            provider.check("Sales go up over the period.", language="en-GB")

        assert given == sorted(
            given, reverse=True
        ), "each attempt should get less time than the last"
        assert sum(given) <= 4.0 and max(given) <= 1.0

    @pytest.mark.parametrize(
        "body", [b"not json at all", b"[1, 2, 3]", b'{"matches": "not a list"}']
    )
    def test_a_malformed_response_never_reaches_the_analyzer_as_data(self, body: bytes):
        def malformed(url, body_, timeout):
            if url.endswith("/v2/languages"):
                return 200, b"[]"
            return 200, body

        provider = self._provider(malformed)
        try:
            report = provider.check("Sales go up over the period.", language="en-GB")
        except GrammarCheckError:
            return  # refused outright, which is the other acceptable answer
        assert report.matches == ()

    def test_a_failure_message_never_names_the_endpoint(self):
        """These strings reach operator logs and a teacher's screen.

        An internal hostname there is a deployment detail travelling towards a
        classroom, and it is never needed to act on the failure.
        """

        def dead(url, body, timeout):
            if url.endswith("/v2/languages"):
                return 200, b"[]"
            raise TimeoutError("timed out")

        provider = LocalLanguageToolProvider(
            settings(
                GRAMMAR_HOST="lt-internal.university.example",
                GRAMMAR_PORT=8081,
                GRAMMAR_API_URL=None,
            ),
            transport=dead,
        )
        provider._healthy, provider._checked_at = True, float("inf")

        with pytest.raises(GrammarCheckError) as raised:
            provider.check("Sales go up over the period.", language="en-GB")

        assert "lt-internal" not in str(raised.value)
        assert "8081" not in str(raised.value)


# ── Request validation ───────────────────────────────────────────────────────


class TestRequestValidation:
    def test_empty_text_is_not_sent_to_the_engine(self):
        calls = []

        def counting(url, body, timeout):
            calls.append(url)
            return 200, b"[]"

        provider = LocalLanguageToolProvider(settings(), transport=counting)
        report = provider.check("   \n  ", language="en-GB")

        assert report.matches == ()
        assert calls == []  # not even a health probe was worth it

    def test_an_over_long_answer_is_truncated_rather_than_refused(self):
        sent = {}

        def capture(url, body, timeout):
            if url.endswith("/v2/languages"):
                return 200, b"[]"
            sent["body"] = body
            return 200, json.dumps({"matches": []}).encode()

        provider = LocalLanguageToolProvider(settings(GRAMMAR_MAX_CHARS=100), transport=capture)
        report = provider.check("word " * 500, language="en-GB")

        assert report.checked_chars == 100
        assert len(sent["body"]) < 2000

    def test_the_configured_language_reaches_the_engine(self):
        sent = {}

        def capture(url, body, timeout):
            if url.endswith("/v2/languages"):
                return 200, b"[]"
            sent["body"] = body
            return 200, json.dumps({"matches": []}).encode()

        provider = LocalLanguageToolProvider(settings(), transport=capture)
        provider.check("Sales go up over the period.", language="en-US")

        assert b"language=en-US" in sent["body"]


# ── Response mapping ─────────────────────────────────────────────────────────


class TestClassification:
    @pytest.mark.parametrize(
        ("rule_id", "expected"),
        [
            ("SUBJECT_VERB_AGREEMENT", "subject_verb_agreement"),
            ("HE_VERB_AGR", "subject_verb_agreement"),
            ("PAST_PARTICIPLE_TENSE", "verb_tense"),
            ("EN_A_VS_AN", "article_use"),
            ("COMMA_BEFORE_AND", "punctuation"),
            ("SENTENCE_FRAGMENT", "sentence_structure"),
            ("ENGLISH_WORD_REPEAT_RULE", "grammar_error"),
        ],
    )
    def test_a_rule_identifier_decides_the_analytics_slug(self, rule_id: str, expected: str):
        # The identifier, not the message: LanguageTool keeps identifiers
        # stable and rewrites messages between releases, and a year of class
        # reports is grouped by this slug.
        assert classify(rule(rule_id)).subtype == expected

    @pytest.mark.parametrize(
        "foreign",
        [
            {
                "id": "MORFOLOGIK_RULE_EN_GB",
                "issueType": "misspelling",
                "category": {"id": "TYPOS"},
            },
            {"id": "TOO_LONG_SENTENCE", "issueType": "style", "category": {"id": "STYLE"}},
            {"id": "PASSIVE_VOICE", "issueType": "style", "category": {"id": "STYLE"}},
            {
                "id": "EN_GB_SIMPLE_REPLACE",
                "issueType": "locale-violation",
                "category": {"id": "MISC"},
            },
        ],
    )
    def test_findings_that_belong_to_another_analyzer_are_dropped(self, foreign: dict):
        """Two analyzers reporting the same ground is how a result page starts
        contradicting itself.

        Spelling has an exemption set built from the curated vocabulary and the
        chart's own labels; LanguageTool has neither and would flag the target
        terms. Register belongs to word usage, which knows the register this
        exercise teaches.
        """
        assert classify(foreign) is None

    def test_an_unrecognised_rule_is_kept_at_the_lowest_useful_grade(self):
        classification = classify(rule("SOME_RULE_NOBODY_HAS_SEEN"))

        assert classification is not None
        assert classification.subtype == "grammar_error"
        assert classification.specific is False

    def test_an_inconsistency_asserts_no_mistake(self):
        # "organise" in one sentence and "organize" in the next is a choice,
        # not an error — and INFO is the rung that says so.
        classification = classify(
            {"id": "X", "issueType": "inconsistency", "category": {"id": "MISC"}}
        )

        assert classification.severity is IssueSeverity.INFO
        assert classification.severity.is_mistake is False

    def test_a_rule_object_missing_every_field_still_classifies(self):
        # A response shape that drifted in an upgrade should cost the findings
        # it broke, not a student's submission.
        assert classify({}).subtype == "grammar_error"

    def test_a_single_replacement_from_a_known_rule_is_the_most_trusted(self):
        known = classify(rule("SUBJECT_VERB_AGREEMENT"))
        unknown = classify(rule("MYSTERY_RULE"))

        assert confidence_for(known, 1) > confidence_for(unknown, 1)
        assert confidence_for(known, 1) > confidence_for(known, 4)
        # Several replacements means the engine could not choose, and a
        # student should not be asked to.
        assert confidence_for(known, 4) == confidence_for(known, 0)


class TestParsing:
    TEXT = "The graph go up and then it fell."

    def test_offsets_index_the_text_that_was_checked(self):
        parsed = parse_matches({"matches": [match(10, 2)]}, self.TEXT)

        assert len(parsed) == 1
        assert self.TEXT[parsed[0].start : parsed[0].end] == "go"
        assert parsed[0].original_text == "go"

    def test_a_span_outside_the_text_is_dropped_not_clamped(self):
        # A clamped span is a confident-looking highlight of an arbitrary
        # region of the student's answer.
        assert parse_matches({"matches": [match(900, 5)]}, self.TEXT) == []

    def test_a_zero_length_span_is_dropped(self):
        assert parse_matches({"matches": [match(4, 0)]}, self.TEXT) == []

    def test_one_malformed_match_does_not_discard_the_others(self):
        payload = {"matches": [{"offset": "not a number"}, match(10, 2), {"rule": None}]}

        assert len(parse_matches(payload, self.TEXT)) == 1

    def test_several_replacements_offer_none(self):
        parsed = parse_matches(
            {"matches": [match(10, 2, replacements=("goes", "went", "going"))]}, self.TEXT
        )

        assert parsed[0].suggested_text is None
        assert parsed[0].explanation  # the finding still stands

    def test_the_message_is_preferred_over_the_short_label(self):
        raw = match(10, 2)
        raw["shortMessage"] = "Grammar"
        raw["message"] = "The verb does not agree with its subject."

        assert parse_matches({"matches": [raw]}, self.TEXT)[0].explanation.startswith("The verb")

    def test_a_match_with_no_message_still_explains_itself(self):
        raw = match(10, 2)
        raw.pop("message")

        assert parse_matches({"matches": [raw]}, self.TEXT)[0].explanation

    def test_utf16_offsets_are_converted_to_python_indices(self):
        """LanguageTool is a Java service and Java counts in UTF-16.

        One emoji in the answer shifts every subsequent offset by one, and
        every highlight after it lands on the wrong words.
        """
        text = "Sales 📈 go up over the period."
        utf16_offset = len("Sales 📈 ".encode("utf-16-le")) // 2

        parsed = parse_matches({"matches": [match(utf16_offset, 2)]}, text)

        assert len(parsed) == 1
        assert text[parsed[0].start : parsed[0].end] == "go"

    def test_plain_text_pays_nothing_for_the_conversion(self):
        parsed = parse_matches({"matches": [match(10, 2)]}, self.TEXT)
        assert parsed[0].start == 10

    def test_a_response_with_no_matches_key_is_empty_not_an_error(self):
        assert parse_matches({}, self.TEXT) == []


# ── Edges that only show up in production ────────────────────────────────────


class TestEdges:
    def test_a_match_refuses_a_confidence_outside_the_scale(self):
        with pytest.raises(ValueError, match="0–1"):
            GrammarMatch(
                subtype="punctuation",
                severity=IssueSeverity.LOW,
                original_text="x",
                explanation="…",
                start=0,
                end=1,
                confidence=1.4,
            )

    def test_an_endpoint_with_a_scheme_but_no_host_is_refused(self):
        with pytest.raises(ValueError, match="host"):
            normalise_endpoint("http://")

    def test_a_budget_already_spent_fails_without_an_attempt(self):
        """A retry loop must not start an attempt it cannot finish.

        Given twenty milliseconds, a request times out having achieved nothing
        except the loss of the rest of the budget.
        """
        attempts = []

        def slow(url, body, timeout):
            # A timeout means the socket waited, so the attempt costs the time
            # it was given. A fake that fails instantly would never exhaust a
            # budget and would leave this branch unreachable.
            attempts.append(timeout)
            time.sleep(timeout)
            raise TimeoutError("timed out")

        client = LanguageToolClient(
            "http://lt.internal:8081", timeout=0.2, retries=5, transport=slow
        )
        with pytest.raises(GrammarCheckError):
            client.check("Sales go up over the period.", language="en-GB")

        assert len(attempts) == 1

    def test_a_server_error_raised_as_an_exception_is_retried(self):
        # urllib raises 5xx rather than returning it, so both shapes have to
        # be recognised as the same transient failure.
        attempts = []

        def failing(url, body, timeout):
            attempts.append(url)
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)

        client = LanguageToolClient(
            "http://lt.internal:8081", timeout=5.0, retries=2, transport=failing
        )
        with pytest.raises(GrammarCheckError):
            client.check("Sales go up over the period.", language="en-GB")

        assert len(attempts) == 3

    def test_a_not_found_status_is_reported_rather_than_retried(self):
        attempts = []

        def missing(url, body, timeout):
            attempts.append(url)
            return 404, b"no such endpoint"

        client = LanguageToolClient(
            "http://lt.internal:8081", timeout=5.0, retries=3, transport=missing
        )
        with pytest.raises(GrammarCheckError, match="404"):
            client.check("Sales go up over the period.", language="en-GB")

        assert len(attempts) == 1

    def test_an_implausibly_large_response_is_refused_unread(self):
        """A checker returning a hundred megabytes is not LanguageTool.

        Parsing it to find that out would be the actual damage.
        """

        def enormous(url, body, timeout):
            return 200, b"x" * (8 * 1024 * 1024 + 10)

        client = LanguageToolClient("http://lt.internal:8081", timeout=5.0, transport=enormous)
        with pytest.raises(GrammarCheckError, match="large"):
            client.check("Sales go up over the period.", language="en-GB")

    def test_a_non_object_entry_in_the_matches_list_is_skipped(self):
        payload = {"matches": ["not an object", match(10, 2), 17]}

        assert len(parse_matches(payload, TestParsing.TEXT)) == 1

    def test_a_foreign_finding_is_dropped_by_the_parser_too(self):
        # Not only by `classify` in isolation: the whole path from a response
        # to a match has to drop it, or the analyzer would report spelling.
        payload = {
            "matches": [
                match(
                    10,
                    2,
                    rule={
                        "id": "MORFOLOGIK_RULE_EN_GB",
                        "issueType": "misspelling",
                        "category": {"id": "TYPOS"},
                    },
                )
            ]
        }

        assert parse_matches(payload, TestParsing.TEXT) == []

    def test_an_offset_past_the_end_of_an_astral_text_is_dropped(self):
        text = "Sales 📈 go up."
        # Far past the end, in a text where the conversion table is real.
        assert parse_matches({"matches": [match(400, 2)]}, text) == []


class TestTheRealTransport:
    """One pass through the default transport, against a socket.

    Everything else here injects a fake, which proves the client's logic and
    nothing about the request it actually builds. A wrong method, a missing
    content type or a timeout that never reaches the socket would all pass
    every other test in this file and fail in production.
    """

    @pytest.fixture
    def server(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                received["body"] = self.rfile.read(length)
                received["content_type"] = self.headers.get("Content-Type")
                received["path"] = self.path
                payload = json.dumps({"matches": [match(10, 2)]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"[]")

            def log_message(self, *args):  # keep the test output readable
                pass

        httpd = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield httpd, received
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_a_real_request_reaches_a_real_server(self, server):
        httpd, received = server
        host, port = httpd.server_address

        provider = LocalLanguageToolProvider(
            settings(GRAMMAR_HOST=host, GRAMMAR_PORT=port, GRAMMAR_API_URL=None)
        )
        report = provider.check("The graph go up and then it fell.", language="en-GB")

        assert provider.is_available() is True
        assert received["path"] == "/v2/check"
        assert received["content_type"] == "application/x-www-form-urlencoded"
        assert b"language=en-GB" in received["body"]
        assert len(report.matches) == 1
        assert report.latency_ms > 0
