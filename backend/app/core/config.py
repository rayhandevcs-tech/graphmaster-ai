"""Typed application settings.

Every value is loaded from the environment and validated eagerly at import
time, so a misconfigured deployment fails at boot rather than on the first
request that happens to need the missing value.

Nothing outside this module reads ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.enums import AnalyzerAudience


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = Field(min_length=32)
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "GraphMaster"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # ── Authentication ───────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Storage ──────────────────────────────────────────────────────────────
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_PATH: str = "./storage"
    STORAGE_PUBLIC_URL: str = "/media"
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_REGION: str | None = None

    # ── Uploads ──────────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_IMAGE_PIXELS: int = 40_000_000

    # ── OCR ──────────────────────────────────────────────────────────────────
    OCR_PROVIDER_ORDER: str = "google_vision,easyocr,tesseract"
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None
    EASYOCR_MODEL_DIR: str | None = None
    EASYOCR_LANGUAGES: str = "en"
    TESSERACT_CMD: str = "tesseract"

    # ── NLP ──────────────────────────────────────────────────────────────────
    SPACY_MODEL: str = "en_core_web_sm"

    # ── Scoring ──────────────────────────────────────────────────────────────
    VOCABULARY_WEIGHT: float = 0.70
    WRITING_WEIGHT: float = 0.30
    TIER_CROWN_MIN: float = 90.0
    TIER_FLOWER_MIN: float = 60.0
    TIER_STEADY_MIN: float = 50.0
    TARGET_WORD_COUNT_MIN: int = 150
    TARGET_WORD_COUNT_MAX: int = 250

    # ── Assessment ───────────────────────────────────────────────────────────
    # Diagnostic only. Nothing here can move a score, a tier or an XP award —
    # see app/assessment/__init__.py.
    ASSESSMENT_ENABLED: bool = True
    #: Which analyzers run, and in what order. Same idiom as OCR_PROVIDER_ORDER.
    ASSESSMENT_ANALYZERS: str = "vocabulary,writing,spelling,sentence,word_usage,graph_accuracy"
    #: Runs and persists, shown to nobody. A dark launch measures real issue
    #: volume and real latency against real answers before a student is shown
    #: a correction that might be wrong.
    ASSESSMENT_DARK_ANALYZERS: str = ""
    #: Surfaced to teachers and administrators, hidden from students. The
    #: middle rung: teachers judge the false-positive rate first.
    ASSESSMENT_TEACHER_ONLY_ANALYZERS: str = ""
    #: Issues below this confidence are recorded but not shown, so a
    #: false-positive rate can be tuned from evidence rather than guessed.
    ASSESSMENT_ISSUE_CONFIDENCE_FLOOR: float = Field(default=0.6, ge=0.0, le=1.0)
    #: Per category, per submission. A wall of corrections teaches nothing.
    ASSESSMENT_MAX_ISSUES_PER_CATEGORY: int = Field(default=25, ge=1)
    #: Observed, not enforced: a CPU-bound analyzer cannot be preempted safely
    #: from another thread, so exceeding this logs a warning and is recorded on
    #: the output. Hard cancellation belongs to whichever provider does I/O.
    ASSESSMENT_ANALYZER_BUDGET_MS: float = Field(default=250.0, gt=0)

    # ── Grammar provider ─────────────────────────────────────────────────────
    # Off by default: the local engine needs a JVM and a ~250MB download, and
    # the remote one posts student writing to a third party. Neither is a
    # decision to make silently inside an image.
    GRAMMAR_PROVIDER: Literal["none", "local", "remote"] = "none"
    GRAMMAR_API_URL: str | None = None
    GRAMMAR_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0)
    GRAMMAR_LANGUAGE: str = "en-GB"

    # ── Gamification ─────────────────────────────────────────────────────────
    XP_PER_SUBMISSION: int = 20
    XP_HIGH_SCORE_BONUS: int = 30
    XP_STREAK_BONUS: int = 50
    HIGH_SCORE_THRESHOLD: float = 80.0
    MAX_LEVEL: int = 100
    PLATFORM_TIMEZONE: str = "UTC"
    LEADERBOARD_CACHE_MINUTES: int = 15

    # ── Rate limiting ────────────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = True

    # ── Derived helpers ──────────────────────────────────────────────────────

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def ocr_provider_order(self) -> list[str]:
        return [p.strip() for p in self.OCR_PROVIDER_ORDER.split(",") if p.strip()]

    def analyzer_audience(self, name: str) -> AnalyzerAudience:
        """Who may see what ``name`` produced.

        The most restrictive listing wins. An analyzer named in both lists is
        a deployment mid-way through a rollback, and answering "teacher" there
        would show a student output that someone has just decided to withdraw.
        """
        if name in self._named("ASSESSMENT_DARK_ANALYZERS"):
            return AnalyzerAudience.DARK
        if name in self._named("ASSESSMENT_TEACHER_ONLY_ANALYZERS"):
            return AnalyzerAudience.TEACHER
        return AnalyzerAudience.STUDENT

    def _named(self, setting: str) -> list[str]:
        """A comma-separated setting, cleaned and de-duplicated in order."""
        seen: dict[str, None] = {}
        for name in str(getattr(self, setting)).split(","):
            cleaned = name.strip()
            if cleaned:
                seen.setdefault(cleaned, None)
        return list(seen)

    @property
    def assessment_analyzers(self) -> list[str]:
        """Configured analyzer names, in order, de-duplicated.

        Duplicates are dropped rather than run twice: an analyzer named twice
        in an environment variable is a typo, and running it twice would
        double every issue it finds.
        """
        return self._named("ASSESSMENT_ANALYZERS")

    @property
    def easyocr_languages(self) -> list[str]:
        return [lang.strip() for lang in self.EASYOCR_LANGUAGES.split(",") if lang.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def sync_database_url(self) -> str:
        """Alembic and the seeding CLI run synchronously; strip the async driver."""
        return self.DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")

    # ── Validation ───────────────────────────────────────────────────────────

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_placeholder_secret(cls, v: str) -> str:
        if "change-me" in v.lower():
            raise ValueError(
                "SECRET_KEY is still the placeholder from .env.example. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return v

    @field_validator("PLATFORM_TIMEZONE")
    @classmethod
    def _known_timezone(cls, v: str) -> str:
        """Reject an unknown zone at boot rather than at the first scoring.

        Every streak boundary and leaderboard window is derived from this, so a
        typo would otherwise surface as a 500 on a student's submission — long
        after whoever deployed it had stopped watching.
        """
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"PLATFORM_TIMEZONE {v!r} is not a known IANA timezone.") from exc
        return v

    @model_validator(mode="after")
    def _check_scoring_weights(self) -> Settings:
        total = self.VOCABULARY_WEIGHT + self.WRITING_WEIGHT
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"VOCABULARY_WEIGHT + WRITING_WEIGHT must equal 1.0, got {total:.4f}")
        return self

    @model_validator(mode="after")
    def _check_tier_thresholds(self) -> Settings:
        if not self.TIER_CROWN_MIN > self.TIER_FLOWER_MIN > self.TIER_STEADY_MIN:
            raise ValueError(
                "Tier thresholds must strictly decrease: "
                "TIER_CROWN_MIN > TIER_FLOWER_MIN > TIER_STEADY_MIN"
            )
        return self

    @model_validator(mode="after")
    def _check_s3_configured(self) -> Settings:
        if self.STORAGE_BACKEND == "s3" and not (self.S3_BUCKET and self.S3_ACCESS_KEY_ID):
            raise ValueError(
                "STORAGE_BACKEND is 's3' but S3_BUCKET and S3_ACCESS_KEY_ID are not both set"
            )
        return self

    @model_validator(mode="after")
    def _check_production_hardening(self) -> Settings:
        if self.is_production and self.DEBUG:
            raise ValueError("DEBUG must be false when ENVIRONMENT is 'production'")
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached accessor. Call this rather than instantiating ``Settings`` directly."""
    return Settings()  # type: ignore[call-arg]
