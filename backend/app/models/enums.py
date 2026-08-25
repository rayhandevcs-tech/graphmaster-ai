"""Domain enumerations.

These are stored as strings with database ``CHECK`` constraints rather than as
PostgreSQL ``ENUM`` types: adding a value later is then an ordinary migration
instead of a type alteration that takes an exclusive lock on every table using
the type.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class GraphType(StrEnum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    AREA = "area"


class Difficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class InputMethod(StrEnum):
    TYPED = "typed"
    HANDWRITING = "handwriting"


class SubmissionStatus(StrEnum):
    DRAFT = "draft"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    ANALYZING = "analyzing"
    SCORED = "scored"
    FAILED = "failed"


class RewardTier(StrEnum):
    CROWN = "crown"
    FLOWER = "flower"
    STEADY = "steady"
    HAMMER = "hammer"


class OCRProviderName(StrEnum):
    GOOGLE_VISION = "google_vision"
    EASYOCR = "easyocr"
    TESSERACT = "tesseract"


class XPReason(StrEnum):
    SUBMISSION = "submission"
    HIGH_SCORE_BONUS = "high_score_bonus"
    STREAK_BONUS = "streak_bonus"
    ACHIEVEMENT = "achievement"
    MANUAL_ADJUSTMENT = "manual_adjustment"


class LeaderboardScope(StrEnum):
    GLOBAL = "global"
    CLASS = "class"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AnalyticsScope(StrEnum):
    PLATFORM = "platform"
    CLASS = "class"
    STUDENT = "student"


class ReportType(StrEnum):
    CLASS_SUMMARY = "class_summary"
    STUDENT_DETAIL = "student_detail"
    VOCABULARY_USAGE = "vocabulary_usage"
    SUBMISSION_EXPORT = "submission_export"


class ReportFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"


class ReportStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class IssueCategory(StrEnum):
    """What kind of problem an assessment issue describes.

    One vocabulary for every analyzer, so the issues from all of them can live
    in one list ordered by where they appear in the answer.
    """

    GRAMMAR = "grammar"
    SPELLING = "spelling"
    SENTENCE = "sentence"
    WORD_USAGE = "word_usage"
    VOCABULARY = "vocabulary"
    GRAPH_ACCURACY = "graph_accuracy"
    STYLE = "style"


class IssueSeverity(StrEnum):
    """How firmly an issue is asserted.

    The distinction is required, not cosmetic: FR asks that acceptable
    stylistic variation is never penalised, so a preference must be able to
    say it is a preference. Only ``ERROR`` claims the student got something
    wrong.
    """

    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class AnalyzerStatus(StrEnum):
    """How one analyzer's run ended.

    ``UNAVAILABLE`` and ``FAILED`` are deliberately different. The first is a
    deployment fact — no grammar provider is configured — and the second is a
    fault. Collapsing them would make "this server cannot check grammar"
    indistinguishable from "the grammar checker crashed", and only one of
    those is worth waking someone for.
    """

    OK = "ok"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    FAILED = "failed"


def values(enum_cls: type[StrEnum]) -> list[str]:
    """Member values, for building ``CHECK`` constraints from the enum itself."""
    return [member.value for member in enum_cls]
