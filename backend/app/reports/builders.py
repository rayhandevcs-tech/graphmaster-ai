"""Turn analytics results into the document each report type describes.

Kept apart from both the queries and the writers, so a report's *shape* — what
columns, in what order, with what caveats — is decided in one readable place
rather than being spread across three format-specific renderers.
"""

from __future__ import annotations

from typing import Any

from app.models.enums import ReportType
from app.reports.table import Column, Document, Table

# Reused wherever a student is listed, so the same person reads the same way in
# every export.
STUDENT_COLUMNS = [
    Column("full_name", "Student"),
    Column("email", "Email"),
    Column("class_name", "Class"),
    Column("submission_count", "Attempts", numeric=True),
    Column("average_final_score", "Average score", numeric=True),
    Column("average_vocabulary_percentage", "Average vocabulary %", numeric=True),
    Column("highest_final_score", "Best score", numeric=True),
    Column("current_level", "Level", numeric=True),
    Column("total_xp", "XP", numeric=True),
    Column("current_streak_days", "Streak", numeric=True),
    Column("last_submission_at", "Last attempt"),
]

SUBMISSION_COLUMNS = [
    Column("student_name", "Student"),
    Column("class_name", "Class"),
    Column("graph_title", "Graph"),
    Column("graph_type", "Type"),
    Column("input_method", "Input"),
    Column("word_count", "Words", numeric=True),
    Column("final_score", "Final score", numeric=True),
    Column("vocabulary_score", "Vocabulary score", numeric=True),
    Column("writing_score", "Writing score", numeric=True),
    Column("vocabulary_percentage", "Vocabulary %", numeric=True),
    Column("terms_used", "Terms used", numeric=True),
    Column("terms_targeted", "Terms targeted", numeric=True),
    Column("reward_tier", "Tier"),
    Column("was_ocr_edited", "OCR corrected"),
    Column("ocr_provider", "OCR engine"),
    Column("submitted_at", "Started"),
    Column("scored_at", "Marked"),
]

VOCABULARY_COLUMNS = [
    Column("term", "Term"),
    Column("category_name", "Category"),
    Column("uses", "Uses", numeric=True),
    Column("submission_count", "Submissions", numeric=True),
    Column("student_count", "Students", numeric=True),
]

TIER_ORDER = ("crown", "flower", "steady", "hammer")

# Stated on every export carrying an average, because the alternative is a
# teacher reading a blank cell as a zero and concluding a student is failing
# when they have simply not started.
NO_WORK_NOTE = "A blank average means the student has no marked work in this period."


def summary_table(overview: dict[str, Any], engagement: dict[str, Any]) -> Table:
    """The headline block: one row per figure, so it survives every format."""
    rows = [
        {"metric": "Marked submissions", "value": overview["submission_count"]},
        {"metric": "Students enrolled", "value": overview["enrolled_student_count"]},
        {"metric": "Students who practised", "value": overview["active_student_count"]},
        {"metric": "Students who did not", "value": engagement["inactive_student_count"]},
        {"metric": "Participation rate (%)", "value": engagement["participation_rate"]},
        {"metric": "Average score", "value": overview["average_final_score"]},
        {"metric": "Average vocabulary (%)", "value": overview["average_vocabulary_percentage"]},
        {"metric": "Highest score", "value": overview["highest_final_score"]},
        {"metric": "Average words written", "value": overview["average_word_count"]},
        {
            "metric": "Attempts per active student",
            "value": engagement["submissions_per_active_student"],
        },
        {"metric": "Students on a streak", "value": engagement["streak_holders"]},
    ]
    return Table(
        name="Summary",
        columns=[Column("metric", "Metric"), Column("value", "Value", numeric=True)],
        rows=rows,
    )


def tier_table(distribution: dict[str, int]) -> Table:
    """The reward-tier spread, listed in tier order rather than by frequency.

    A fixed order lets a teacher compare two classes at a glance; sorting by
    count would move the rows between reports and defeat that.
    """
    total = sum(distribution.values())
    return Table(
        name="Reward tiers",
        columns=[
            Column("tier", "Tier"),
            Column("count", "Submissions", numeric=True),
            Column("share", "Share (%)", numeric=True),
        ],
        rows=[
            {
                "tier": tier,
                "count": distribution.get(tier, 0),
                "share": round(distribution.get(tier, 0) / total * 100, 1) if total else 0.0,
            }
            for tier in TIER_ORDER
        ],
    )


def trend_table(points: list[dict[str, Any]]) -> Table:
    return Table(
        name="Score trend",
        columns=[
            Column("date", "Date"),
            Column("submission_count", "Submissions", numeric=True),
            Column("average_final_score", "Average score", numeric=True),
            Column("average_vocabulary_percentage", "Average vocabulary %", numeric=True),
        ],
        rows=points,
    )


def class_summary(data: dict[str, Any], *, meta: dict[str, str], timezone: str) -> Document:
    """The report a teacher shows a department head (FR-11.3)."""
    return Document(
        title="Class summary",
        subtitle=data.get("class_name") or "All classes",
        meta=meta,
        timezone=timezone,
        tables=[
            summary_table(data, data["engagement"]),
            tier_table(data["reward_tier_distribution"]),
            Table(
                name="Students",
                columns=STUDENT_COLUMNS,
                rows=data["students"],
                note=NO_WORK_NOTE,
            ),
            trend_table(data["trend"]),
        ],
    )


def student_detail(
    data: dict[str, Any],
    *,
    submissions: list[dict[str, Any]],
    meta: dict[str, str],
    timezone: str,
) -> Document:
    """One student's full record (FR-11.2)."""
    student = data["students"][0] if data["students"] else {}
    return Document(
        title="Student report",
        subtitle=student.get("full_name", "Student"),
        meta=meta,
        timezone=timezone,
        tables=[
            summary_table(data, data["engagement"]),
            Table(name="Attempts", columns=SUBMISSION_COLUMNS, rows=submissions),
            trend_table(data["trend"]),
        ],
    )


def vocabulary_usage(data: dict[str, Any], *, meta: dict[str, str], timezone: str) -> Document:
    """Which target terms are landing and which are not (FR-11.4)."""
    return Document(
        title="Vocabulary usage",
        subtitle=f"{data['used_term_count']} of {data['term_count']} terms used",
        meta=meta,
        timezone=timezone,
        tables=[
            Table(name="Most used", columns=VOCABULARY_COLUMNS, rows=data["most_used"]),
            Table(
                name="Least used",
                columns=VOCABULARY_COLUMNS,
                rows=data["least_used"],
                note=(
                    "Terms with zero uses are the ones nobody reached for at all — "
                    "usually the most useful place to teach next."
                ),
            ),
        ],
    )


def submission_export(
    rows: list[dict[str, Any]], *, meta: dict[str, str], timezone: str
) -> Document:
    """The raw rows, for a spreadsheet or a statistics package."""
    return Document(
        title="Submission export",
        subtitle=f"{len(rows)} marked submissions",
        meta=meta,
        timezone=timezone,
        tables=[Table(name="Submissions", columns=SUBMISSION_COLUMNS, rows=rows)],
    )


TITLES = {
    ReportType.CLASS_SUMMARY: "Class summary",
    ReportType.STUDENT_DETAIL: "Student report",
    ReportType.VOCABULARY_USAGE: "Vocabulary usage",
    ReportType.SUBMISSION_EXPORT: "Submission export",
}
