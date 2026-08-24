"""Report rendering: one document description, three output formats."""

from __future__ import annotations

from app.models.enums import ReportFormat
from app.reports import csv_writer, pdf_writer, xlsx_writer
from app.reports.table import Column, Document, Table

CONTENT_TYPES = {
    ReportFormat.CSV: "text/csv; charset=utf-8",
    ReportFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ReportFormat.PDF: "application/pdf",
}

EXTENSIONS = {
    ReportFormat.CSV: "csv",
    ReportFormat.XLSX: "xlsx",
    ReportFormat.PDF: "pdf",
}

_RENDERERS = {
    ReportFormat.CSV: csv_writer.render,
    ReportFormat.XLSX: xlsx_writer.render,
    ReportFormat.PDF: pdf_writer.render,
}


def render(document: Document, fmt: ReportFormat) -> bytes:
    """Render a document. Raises ``ServiceUnavailableError`` for a format whose
    optional dependency is not installed on this server."""
    return _RENDERERS[fmt](document)


def available_formats() -> list[ReportFormat]:
    """The formats this deployment can actually produce.

    Published on the endpoint so a client can hide an Excel button that would
    only ever return 503, rather than offering it and apologising afterwards.
    """
    formats = [ReportFormat.CSV]
    if xlsx_writer.AVAILABLE:
        formats.append(ReportFormat.XLSX)
    if pdf_writer.AVAILABLE:
        formats.append(ReportFormat.PDF)
    return formats


__all__ = [
    "CONTENT_TYPES",
    "EXTENSIONS",
    "Column",
    "Document",
    "Table",
    "available_formats",
    "render",
]
