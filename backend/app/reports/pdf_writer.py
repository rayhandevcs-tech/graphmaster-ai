"""PDF rendering, via the optional ``reportlab`` dependency.

The PDF is the format a teacher prints or attaches to an email, so it carries
the header block and page numbers a CSV cannot. It is also the one a reader
cannot re-sort, which is why the builders decide the row order rather than
leaving it to the reader.
"""

from __future__ import annotations

import io
from typing import Any

from app.core.exceptions import ServiceUnavailableError
from app.reports.table import Document, Table, to_text

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle
    from reportlab.platypus import Table as Grid

    AVAILABLE = True
except ImportError:  # pragma: no cover - depends on what is installed
    AVAILABLE = False

BRAND = "#6D28D9"
BAND = "#f5f3ff"
RULE = "#d1d5db"
MUTED = "#4b5563"


def render(document: Document) -> bytes:
    if not AVAILABLE:  # pragma: no cover - depends on what is installed
        raise ServiceUnavailableError(
            "PDF export is not available on this server. Export as CSV instead."
        )

    stream = io.BytesIO()
    # Landscape, because a submission export is a wide table and a portrait
    # page shrinks it to unreadable type.
    template = SimpleDocTemplate(
        stream,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=document.title,
        author="GraphMaster",
    )
    template.build(_story(document), onFirstPage=_footer, onLaterPages=_footer)
    return stream.getvalue()


def _styles() -> dict[str, Any]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title_", parent=base["Title"], fontSize=18, spaceAfter=4),
        "muted": ParagraphStyle(
            "Muted", parent=base["Normal"], fontSize=10, textColor=colors.HexColor(MUTED)
        ),
        "section": ParagraphStyle("Section", parent=base["Heading2"], fontSize=13, spaceBefore=10),
        # Cells are Paragraphs rather than bare strings so a long graph title
        # wraps inside its column instead of overflowing across the page.
        "cell": ParagraphStyle("Cell", parent=base["Normal"], fontSize=7.5, leading=9.5),
    }


def _story(document: Document) -> list[Any]:
    styles = _styles()
    meta = {"Generated": to_text(document.generated_at, document.timezone)} | document.meta

    story: list[Any] = [Paragraph(escape(document.title), styles["title"])]
    if document.subtitle:
        story.append(Paragraph(escape(document.subtitle), styles["muted"]))
    story.append(
        Paragraph(
            " &nbsp;·&nbsp; ".join(
                f"<b>{escape(label)}:</b> {escape(value)}" for label, value in meta.items()
            ),
            styles["muted"],
        )
    )
    story.append(Spacer(1, 6 * mm))

    for index, table in enumerate(document.tables):
        if index:
            story.append(PageBreak())
        story.append(Paragraph(escape(table.name), styles["section"]))
        story.append(Spacer(1, 2 * mm))
        story.append(_grid(table, styles["cell"], document.timezone))
        if table.note:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(escape(table.note), styles["muted"]))

    return story


def _grid(table: Table, cell: Any, timezone: str) -> Any:
    header = [Paragraph(f"<b>{escape(column.label)}</b>", cell) for column in table.columns]
    body = [
        [Paragraph(escape(to_text(value, timezone)), cell) for value in table.values(row)]
        for row in table.rows
    ]
    # An empty section prints one em-dash row rather than a bare heading, so
    # "no data" is visibly an answer instead of looking like a broken export.
    rows = [header, *body] if body else [header, [Paragraph("—", cell)] * len(table.columns)]

    grid = Grid(rows, repeatRows=1, hAlign="LEFT")
    grid.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(RULE)),
                # Banding rather than heavier rules: a forty-row class list is
                # read across, and the eye needs the row it is on held.
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(BAND)]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return grid


def _footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillGray(0.45)
    canvas.drawString(14 * mm, 8 * mm, "GraphMaster")
    canvas.drawRightString(doc.pagesize[0] - 14 * mm, 8 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def escape(value: Any) -> str:
    """Escape text before it reaches a Paragraph.

    ReportLab parses paragraph text as markup, so student-authored content —
    names, graph titles — has to be escaped or a stray ``&`` fails the build.
    """
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
