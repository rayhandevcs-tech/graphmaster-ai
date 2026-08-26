"""Settings validation.

The point of eager validation is that a misconfigured deployment fails at boot
rather than on the first request that happens to need the bad value.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.models.enums import AnalyzerAudience

BASE = {
    "SECRET_KEY": "a-perfectly-fine-secret-key-over-32-chars",
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
}


def make(**overrides) -> Settings:
    return Settings(**{**BASE, **overrides})


class TestValidation:
    def test_defaults_are_valid(self):
        s = make()
        assert s.VOCABULARY_WEIGHT == 0.70
        assert s.WRITING_WEIGHT == 0.30
        assert s.MAX_LEVEL == 100

    def test_short_secret_key_rejected(self):
        with pytest.raises(ValidationError):
            make(SECRET_KEY="too-short")

    def test_placeholder_secret_key_rejected(self):
        # The .env.example placeholder is long enough to pass the length check,
        # so it needs its own guard or it would ship to production.
        with pytest.raises(ValidationError, match="placeholder"):
            make(SECRET_KEY="change-me-to-a-long-random-string-abcdefgh")

    def test_scoring_weights_must_sum_to_one(self):
        with pytest.raises(ValidationError, match=r"must equal 1\.0"):
            make(VOCABULARY_WEIGHT=0.8, WRITING_WEIGHT=0.3)

    def test_custom_weights_summing_to_one_accepted(self):
        s = make(VOCABULARY_WEIGHT=0.6, WRITING_WEIGHT=0.4)
        assert s.VOCABULARY_WEIGHT == 0.6

    def test_tier_thresholds_must_decrease(self):
        with pytest.raises(ValidationError, match="strictly decrease"):
            make(TIER_CROWN_MIN=50, TIER_FLOWER_MIN=60, TIER_STEADY_MIN=70)

    def test_s3_backend_requires_credentials(self):
        with pytest.raises(ValidationError, match="S3_BUCKET"):
            make(STORAGE_BACKEND="s3")

    def test_s3_backend_with_credentials_accepted(self):
        s = make(STORAGE_BACKEND="s3", S3_BUCKET="b", S3_ACCESS_KEY_ID="k")
        assert s.STORAGE_BACKEND == "s3"

    def test_debug_forbidden_in_production(self):
        with pytest.raises(ValidationError, match="DEBUG must be false"):
            make(ENVIRONMENT="production", DEBUG=True)

    def test_production_without_debug_accepted(self):
        assert make(ENVIRONMENT="production", DEBUG=False).is_production


class TestDerivedProperties:
    def test_cors_origins_split_and_trimmed(self):
        s = make(ALLOWED_ORIGINS="http://a.com, http://b.com ,")
        assert s.cors_origins == ["http://a.com", "http://b.com"]

    def test_ocr_provider_order_parsed(self):
        s = make(OCR_PROVIDER_ORDER="easyocr, tesseract")
        assert s.ocr_provider_order == ["easyocr", "tesseract"]

    def test_max_upload_bytes(self):
        assert make(MAX_UPLOAD_SIZE_MB=10).max_upload_bytes == 10 * 1024 * 1024

    def test_sync_url_strips_async_driver(self):
        # Alembic and the seeding CLI are synchronous and cannot use asyncpg.
        s = make(DATABASE_URL="postgresql+asyncpg://u:p@h:5432/db")
        assert s.sync_database_url == "postgresql://u:p@h:5432/db"


class TestPlatformTimezone:
    def test_an_unknown_timezone_is_refused_at_boot(self):
        """Every gamification date derives from this.

        A typo would otherwise surface days later as a cohort whose streaks
        rolled over at the wrong hour — long after whoever deployed it had
        stopped watching.
        """
        with pytest.raises(ValidationError, match="not a known IANA timezone"):
            make(PLATFORM_TIMEZONE="Asia/Dacca-typo")

    def test_a_real_timezone_is_accepted(self):
        assert make(PLATFORM_TIMEZONE="Asia/Dhaka").PLATFORM_TIMEZONE == "Asia/Dhaka"


class TestOptionalEngineSettings:
    def test_easyocr_languages_are_parsed_into_a_list(self):
        """EasyOCR takes a list; the environment can only carry a string."""
        assert make(EASYOCR_LANGUAGES="en, bn").easyocr_languages == ["en", "bn"]

    def test_a_trailing_separator_does_not_produce_an_empty_language(self):
        assert make(EASYOCR_LANGUAGES="en,").easyocr_languages == ["en"]


class TestGrammarProvider:
    """The one setting whose value sends student writing outside the building."""

    def test_the_default_is_no_grammar_provider(self):
        # Neither engine is a decision to make silently inside an image: the
        # local one needs a JVM and a large download, and the remote one posts
        # student writing to a third party.
        assert make().GRAMMAR_PROVIDER == "none"

    def test_remote_without_an_endpoint_is_refused_at_boot(self):
        """Deliberately fatal rather than a quiet fall back to 'none'.

        Choosing 'remote' is a decision that student writing leaves the
        institution, and a deployment that made it needs to know immediately
        if it is not actually happening — a server quietly running without the
        checker someone switched on would look identical to one that had it.
        """
        with pytest.raises(ValidationError, match="GRAMMAR_API_URL"):
            make(GRAMMAR_PROVIDER="remote")

    def test_remote_with_an_endpoint_is_accepted(self):
        assert (
            make(
                GRAMMAR_PROVIDER="remote", GRAMMAR_API_URL="https://api.example.test"
            ).GRAMMAR_PROVIDER
            == "remote"
        )

    def test_local_needs_no_endpoint_because_it_has_a_host_and_a_port(self):
        settings = make(GRAMMAR_PROVIDER="local")

        assert (settings.GRAMMAR_HOST, settings.GRAMMAR_PORT) == ("localhost", 8081)

    def test_an_unknown_provider_name_is_refused(self):
        with pytest.raises(ValidationError):
            make(GRAMMAR_PROVIDER="chatgpt")

    def test_the_timeout_is_bounded_at_both_ends(self):
        """It is a *total* budget, spent inside the request that scores a
        submission. An unbounded one is an unbounded stall."""
        with pytest.raises(ValidationError):
            make(GRAMMAR_TIMEOUT_SECONDS=0)
        with pytest.raises(ValidationError):
            make(GRAMMAR_TIMEOUT_SECONDS=120)

    def test_the_retry_count_is_bounded(self):
        with pytest.raises(ValidationError):
            make(GRAMMAR_MAX_RETRIES=50)

    def test_grammar_is_in_the_default_analyzer_roster(self):
        # Configured but unavailable is a different fact from absent: it is
        # what lets a result say "grammar was not checked here" rather than
        # implying the writing was clean.
        assert "grammar" in make().assessment_analyzers


class TestTheStudentFloor:
    """C2: a student never sees their own writing profile.

    The staged-rollout lists are how an analyzer is *withdrawn* from an
    audience. They cannot be how it is kept out of one, because the default
    for an analyzer nobody named is ``STUDENT`` — right for the six that
    produce corrections a student should read, and catastrophic for one whose
    whole point is that they must not see it.
    """

    def test_the_profile_analyzer_can_never_be_student_visible(self):
        """Under every configuration, including the ones that get it wrong."""
        configurations = [
            # Nothing named at all — the case a deployment falls into by
            # forgetting a variable, and the one the floor exists for.
            {},
            {"ASSESSMENT_DARK_ANALYZERS": "", "ASSESSMENT_TEACHER_ONLY_ANALYZERS": ""},
            # Named correctly.
            {"ASSESSMENT_TEACHER_ONLY_ANALYZERS": "writing_profile"},
            # Named in a list of other analyzers, but not its own.
            {"ASSESSMENT_TEACHER_ONLY_ANALYZERS": "grammar,spelling"},
            # Someone has explicitly tried to promote it. The environment does
            # not get to make this call.
            {
                "ASSESSMENT_TEACHER_ONLY_ANALYZERS": "grammar",
                "ASSESSMENT_ANALYZERS": "writing_profile",
            },
        ]

        for overrides in configurations:
            audience = make(**overrides).analyzer_audience("writing_profile")
            assert audience is not AnalyzerAudience.STUDENT, (
                f"writing_profile resolved to {audience} under {overrides}. "
                f"No environment may raise it to student visibility."
            )

    def test_the_floor_still_allows_it_to_be_pushed_dark(self):
        """The floor stops promotion, not withdrawal.

        A dark launch is the stage before teacher visibility, so the most
        restrictive listing has to keep winning — otherwise the floor would
        force output onto teachers during the stage that exists to check it
        before anyone sees it.
        """
        s = make(ASSESSMENT_DARK_ANALYZERS="writing_profile")

        assert s.analyzer_audience("writing_profile") is AnalyzerAudience.DARK

    def test_the_floor_does_not_touch_the_other_analyzers(self):
        s = make()

        for name in ("vocabulary", "writing", "spelling", "sentence", "grammar"):
            assert s.analyzer_audience(name) is AnalyzerAudience.STUDENT

    def test_the_profile_analyzer_is_not_in_the_default_roster(self):
        """Measurement is switched on per deployment, never by pulling a release."""
        assert "writing_profile" not in make().assessment_analyzers

    def test_the_comparison_layer_is_off_by_default(self):
        assert make().CONSISTENCY_ANALYTICS_ENABLED is False

    def test_the_word_floor_sits_below_the_target_minimum(self):
        """A slightly short answer is still profiled; a fragment is not."""
        s = make()

        assert s.CONSISTENCY_MIN_WORDS < s.TARGET_WORD_COUNT_MIN

    def test_a_baseline_of_one_is_refused(self):
        # A "baseline" from a single prior submission is that submission, and
        # a difference from it is noise with a decimal point.
        with pytest.raises(ValidationError):
            make(CONSISTENCY_MIN_BASELINE=1)
