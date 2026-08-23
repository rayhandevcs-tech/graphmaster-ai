"""Settings validation.

The point of eager validation is that a misconfigured deployment fails at boot
rather than on the first request that happens to need the bad value.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

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
