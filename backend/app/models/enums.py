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
    """How much an issue matters, on one ordered scale.

    ``INFO`` is not the bottom of a severity ladder — it is the rung that
    means **"this is not a mistake"**. The specification asks that acceptable
    stylistic variation is never penalised, so a preference has to be able to
    say it is a preference; :attr:`is_mistake` makes that a property of the
    type rather than a convention an analyzer author has to remember.

    The three grades above it all assert the student got something wrong, and
    differ only in how much it costs them:

    * ``LOW`` — worth knowing, and the reader would not have stumbled.
    * ``MEDIUM`` — a real error against the conventions being taught.
    * ``HIGH`` — it changes what the writing means, or contradicts the data.
    """

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        """Sort key. ``StrEnum`` orders alphabetically, which is meaningless here."""
        return _SEVERITY_RANK[self]

    @property
    def is_mistake(self) -> bool:
        """Whether this asserts the student did something wrong.

        The one guard that keeps a style preference from reading as an error,
        wherever it is counted or displayed.
        """
        return self is not IssueSeverity.INFO


#: Declared after the class because a ``StrEnum`` body cannot hold a mapping of
#: its own members.
_SEVERITY_RANK: dict[IssueSeverity, int] = {
    IssueSeverity.INFO: 0,
    IssueSeverity.LOW: 1,
    IssueSeverity.MEDIUM: 2,
    IssueSeverity.HIGH: 3,
}


class AssessmentStatus(StrEnum):
    """How complete one submission's assessment is.

    ``PENDING`` is reserved from the first migration for the deferred pass
    that expensive analyzers will need. Adding it later would mean altering a
    ``CHECK`` constraint on a table with rows in it; adding it now costs
    nothing.

    ``PARTIAL`` means an analyzer *failed*. One that is simply not configured
    on this server leaves the assessment ``COMPLETE`` — a deployment fact is
    not a fault, and conflating them would leave every server without a
    grammar provider permanently reporting partial results.
    """

    PENDING = "pending"
    COMPLETE = "complete"
    PARTIAL = "partial"


class ClaimVerdict(StrEnum):
    """Whether a claim about the chart matched the data.

    ``UNVERIFIED`` is the honest majority case: the sentence could not be
    resolved to a series with enough confidence to judge it. It is stored
    rather than dropped because "we could not check this" and "we checked it
    and it was fine" are different, and only one of them should encourage a
    student.
    """

    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNVERIFIED = "unverified"


class ClaimType(StrEnum):
    """What kind of statement about the chart a claim makes."""

    TREND = "trend"
    PEAK = "peak"
    TROUGH = "trough"
    COMPARISON = "comparison"
    MAGNITUDE = "magnitude"
    TIMING = "timing"


class AnalyzerAudience(StrEnum):
    """Who may see what an analyzer produced.

    Staged rollout, per analyzer, without a redeploy. An analyzer moves
    ``dark`` → ``teacher`` → ``student`` as confidence in its false-positive
    rate grows, and moves back the moment it does not.

    ``DARK`` still runs and still persists: the point of a dark launch is to
    measure real issue volume and real latency against real answers before
    anyone is shown a correction that might be wrong.
    """

    STUDENT = "student"
    TEACHER = "teacher"
    DARK = "dark"


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
