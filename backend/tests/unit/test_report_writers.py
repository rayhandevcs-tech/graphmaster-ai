"""Rendering one document description into three formats.

No database here. These are about what each writer does with the awkward
cases — an empty table, a null average, a student whose name contains an
ampersand, a section name Excel will not accept.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models.enums import ReportFormat
from app.reports import CONTENT_TYPES, EXTENSIONS, available_formats, render
from app.reports.table import Column, Document, Table, to_native, to_text

openpyxl = pytest.importorskip("openpyxl")


def document(**overrides) -> Document:
    base = {
        "title": "Class summary",
        "subtitle": "Section A & B",
        "meta": {"Class": "Section A", "Period": "All time"},
        "generated_at": datetime(2026, 8, 24, 9, 30, tzinfo=UTC),
        "tables": [
            Table(
                name="Students",
                columns=[
                    Column("full_name", "Student"),
                    Column("average_final_score", "Average score", numeric=True),
                    Column("last_submission_at", "Last attempt"),
                ],
                rows=[
                    {
                        "full_name": "Zoë & Co",
                        "average_final_score": Decimal("91.50"),
                        "last_submission_at": datetime(2026, 8, 20, 14, 5, tzinfo=UTC),
                    },
                    {
                        "full_name": "Never Started",
                        "average_final_score": None,
                        "last_submission_at": None,
                    },
                ],
                note="A blank average means no marked work.",
            )
        ],
    }
    return Document(**(base | overrides))


# ── Cell formatting ──────────────────────────────────────────────────────────


def test_a_missing_average_renders_blank_not_zero():
    """Zero would place someone who has not started below someone scoring badly."""
    assert to_text(None) == ""
    assert to_native(None) is None


def test_a_decimal_is_rendered_as_a_number_in_both_forms():
    assert to_text(Decimal("91.50")) == "91.5"
    assert to_native(Decimal("91.50")) == 91.5


def test_booleans_read_as_words_in_text_formats():
    """ "True" in a spreadsheet column headed "OCR corrected" reads as noise."""
    assert to_text(True) == "yes"
    assert to_text(False) == "no"
    # The workbook keeps the real boolean, which Excel can filter on.
    assert to_native(True) is True


def test_a_timestamp_keeps_its_offset_in_text():
    moment = datetime(2026, 8, 20, 14, 5, tzinfo=UTC)

    assert to_text(moment) == "2026-08-20 14:05:00+00:00"
    # A datetime in the workbook, so a column can be sorted — but naive,
    # because Excel has no concept of an offset and openpyxl refuses to write
    # an aware one rather than silently guessing.
    assert to_native(moment) == datetime(2026, 8, 20, 14, 5)
    assert to_native(moment).tzinfo is None


def test_timestamps_are_rendered_in_the_report_timezone():
    """A report read in Dhaka should show Dhaka times, not UTC."""
    moment = datetime(2026, 8, 20, 20, 30, tzinfo=UTC)

    assert to_text(moment, "Asia/Dhaka").startswith("2026-08-21 02:30:00")
    assert to_native(moment, "Asia/Dhaka") == datetime(2026, 8, 21, 2, 30)


def test_a_naive_value_passes_through_untouched():
    """Dates carry no zone, so converting one would shift it by a day."""
    assert to_text(date(2026, 8, 20), "Asia/Dhaka") == "2026-08-20"


# ── CSV ──────────────────────────────────────────────────────────────────────


def test_csv_carries_the_header_block_before_the_table():
    """A file of bare column names cannot be identified in a downloads folder."""
    text = render(document(), ReportFormat.CSV).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))

    assert rows[0] == ["Class summary"]
    assert rows[1] == ["Section A & B"]
    assert ["Class", "Section A"] in rows
    assert ["Students"] in rows


def test_csv_starts_with_a_byte_order_mark():
    """Without it Excel renders "Zoë" as "ZoÃ«" and the teacher distrusts the lot."""
    payload = render(document(), ReportFormat.CSV)

    assert payload.startswith(b"\xef\xbb\xbf")
    assert "Zoë & Co" in payload.decode("utf-8-sig")


def test_csv_stacks_multiple_tables_with_their_names():
    doc = document(
        tables=[
            Table("First", [Column("a", "A")], [{"a": 1}]),
            Table("Second", [Column("b", "B")], [{"b": 2}]),
        ]
    )

    rows = list(csv.reader(io.StringIO(render(doc, ReportFormat.CSV).decode("utf-8-sig"))))

    assert ["First"] in rows
    assert ["Second"] in rows


def test_csv_writes_an_empty_cell_for_a_student_with_no_work():
    rows = list(csv.reader(io.StringIO(render(document(), ReportFormat.CSV).decode("utf-8-sig"))))
    started = next(row for row in rows if row and row[0] == "Never Started")

    assert started[1] == ""


# ── XLSX ─────────────────────────────────────────────────────────────────────


def load(payload: bytes):
    return openpyxl.load_workbook(io.BytesIO(payload))


def test_the_workbook_opens_on_a_sheet_explaining_what_it_is():
    workbook = load(render(document(), ReportFormat.XLSX))

    assert workbook.sheetnames[0] == "About"
    assert workbook["About"]["A1"].value == "Class summary"


def test_numbers_stay_numbers_in_the_workbook():
    """A score written as text cannot be sorted, averaged or charted."""
    sheet = load(render(document(), ReportFormat.XLSX))["Students"]

    assert sheet["B2"].value == 91.5
    assert isinstance(sheet["B2"].value, float)
    assert sheet["B3"].value is None


def test_the_header_row_is_frozen_and_filterable():
    """A forty-row class list is unusable without both."""
    sheet = load(render(document(), ReportFormat.XLSX))["Students"]

    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref is not None


def test_a_sheet_name_too_long_for_excel_is_truncated():
    doc = document(tables=[Table("A" * 60, [Column("a", "A")], [{"a": 1}])])

    workbook = load(render(doc, ReportFormat.XLSX))

    assert all(len(name) <= 31 for name in workbook.sheetnames)


def test_two_tables_that_truncate_to_the_same_name_still_both_appear():
    doc = document(
        tables=[
            Table("Submissions by " + "x" * 40, [Column("a", "A")], [{"a": 1}]),
            Table("Submissions by " + "x" * 41, [Column("a", "A")], [{"a": 2}]),
        ]
    )

    workbook = load(render(doc, ReportFormat.XLSX))

    assert len(workbook.sheetnames) == 3  # About + both tables
    assert len(set(workbook.sheetnames)) == 3


def test_a_sheet_name_with_characters_excel_rejects_is_cleaned():
    doc = document(tables=[Table("Scores [2026]/Q1", [Column("a", "A")], [{"a": 1}])])

    workbook = load(render(doc, ReportFormat.XLSX))

    assert not any(set(name) & set(r"[]:*?/\\") for name in workbook.sheetnames)


# ── PDF ──────────────────────────────────────────────────────────────────────


def test_the_pdf_is_a_pdf():
    payload = render(document(), ReportFormat.PDF)

    assert payload.startswith(b"%PDF")
    assert len(payload) > 1000


def test_an_ampersand_in_a_student_name_does_not_break_the_build():
    """ReportLab parses cell text as markup, so it has to be escaped."""
    doc = document(
        tables=[
            Table(
                "Students",
                [Column("n", "Name")],
                [{"n": "Ben & Jerry <script>"}, {"n": "A > B"}],
            )
        ]
    )

    assert render(doc, ReportFormat.PDF).startswith(b"%PDF")


def test_an_empty_table_still_renders_a_page():
    """ "No data" has to be visibly an answer, not a broken export."""
    doc = document(tables=[Table("Students", [Column("n", "Name")], [])])

    assert render(doc, ReportFormat.PDF).startswith(b"%PDF")


def test_a_document_with_no_tables_at_all_still_renders():
    for fmt in available_formats():
        assert render(document(tables=[]), fmt)


# ── Capabilities ─────────────────────────────────────────────────────────────


def test_csv_is_always_available():
    """It needs nothing beyond the standard library."""
    assert ReportFormat.CSV in available_formats()


def test_every_available_format_has_a_content_type_and_extension():
    for fmt in available_formats():
        assert fmt in CONTENT_TYPES
        assert fmt in EXTENSIONS


def test_a_date_column_is_not_formatted_as_a_timestamp():
    """openpyxl widens a date to a datetime, so the format has to come from
    the source value — otherwise every trend row shows a meaningless 00:00."""
    doc = document(
        tables=[
            Table("Trend", [Column("d", "Date")], [{"d": date(2026, 8, 24)}]),
            Table(
                "Stamps",
                [Column("t", "At")],
                [{"t": datetime(2026, 8, 24, 14, 5, tzinfo=UTC)}],
            ),
        ]
    )

    workbook = load(render(doc, ReportFormat.XLSX))

    assert workbook["Trend"]["A2"].number_format == "yyyy-mm-dd"
    assert workbook["Stamps"]["A2"].number_format == "yyyy-mm-dd hh:mm"


def test_a_column_with_no_dates_keeps_the_default_format():
    doc = document(tables=[Table("Scores", [Column("s", "Score", numeric=True)], [{"s": 91.5}])])

    assert load(render(doc, ReportFormat.XLSX))["Scores"]["A2"].number_format == "General"
