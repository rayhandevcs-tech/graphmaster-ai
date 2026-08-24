"""The shape every export is rendered from.

One structure, three writers. A report is described once — as a title, some
context lines and a list of tables — and CSV, XLSX and PDF each render that
description in their own idiom. The alternative, a query per format, is how
three exports of "the same" data end up quietly disagreeing with each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    numeric: bool = False
    """Right-aligned in the PDF, and written as a real number in the workbook
    so Excel can sort and chart it rather than treating it as text."""


@dataclass(frozen=True)
class Table:
    name: str
    columns: list[Column]
    rows: list[dict[str, Any]]
    note: str | None = None
    """Shown under the table. Where a number needs a caveat, it belongs next to
    the number, not in a covering email nobody keeps."""

    def values(self, row: dict[str, Any]) -> list[Any]:
        return [row.get(column.key) for column in self.columns]


@dataclass(frozen=True)
class Document:
    title: str
    subtitle: str = ""
    meta: dict[str, str] = field(default_factory=dict)
    """Scope, period, filters — what the reader needs to know before believing
    a single figure in the tables."""

    tables: list[Table] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    timezone: str = "UTC"
    """The zone every timestamp in the document is rendered in.

    Every stored timestamp is ``timestamptz``, and a report read by a teacher
    in Dhaka should show Dhaka times. It is also a hard requirement for the
    workbook: Excel has no concept of an offset and openpyxl refuses to write
    an aware datetime at all.
    """


def localise(value: Any, timezone: str) -> Any:
    """Move an aware timestamp into the report's timezone.

    Naive values and non-timestamps pass through untouched, so this is safe to
    apply to every cell.
    """
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(ZoneInfo(timezone))
    return value


def to_text(value: Any, timezone: str = "UTC") -> str:
    """Render one cell for a text-based format.

    ``None`` becomes an empty cell rather than "None" or ``0``: a student with
    no marked work has no average, and printing a zero would place them below
    someone who scored badly — a different and unfair statement.
    """
    value = localise(value, timezone)
    if value is None:
        return ""
    if isinstance(value, bool):
        # "True" under a column headed "OCR corrected" reads as debug output.
        return "yes" if value else "no"
    if isinstance(value, Decimal):
        return f"{float(value):g}"
    if isinstance(value, datetime):
        # Seconds are enough for a report, and the offset is kept so a reader
        # elsewhere can tell what the timestamps mean.
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def to_native(value: Any, timezone: str = "UTC") -> Any:
    """Render one cell for a format with real types (the workbook).

    Numbers stay numbers and dates stay dates, so a teacher can sort a column
    or drop a chart on it. The offset is **dropped** after converting: Excel
    has no concept of one, and openpyxl refuses to write an aware datetime
    rather than silently guessing. The cover sheet names the timezone instead.
    """
    value = localise(value, timezone)
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if value is None or isinstance(value, bool | int | float | date):
        return value
    if isinstance(value, Decimal):
        return float(value)
    return str(value)
