"""CSV rendering. Standard library only, so it is always available."""

from __future__ import annotations

import csv
import io

from app.reports.table import Document, to_text


def render(document: Document) -> bytes:
    """One flat file, tables stacked with a blank line between them.

    A workbook's worth of structure does not survive CSV, so the header block
    and the section names are written as ordinary rows rather than dropped: a
    file that opens with nothing but column headings cannot be identified once
    it is sitting in someone's downloads folder.
    """
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")

    writer.writerow([document.title])
    if document.subtitle:
        writer.writerow([document.subtitle])
    writer.writerow(["Generated", to_text(document.generated_at, document.timezone)])
    for label, value in document.meta.items():
        writer.writerow([label, value])

    for table in document.tables:
        writer.writerow([])
        writer.writerow([table.name])
        writer.writerow([column.label for column in table.columns])
        for row in table.rows:
            writer.writerow([to_text(value, document.timezone) for value in table.values(row)])
        if table.note:
            writer.writerow([table.note])

    # Encoded with a BOM so Excel opens a UTF-8 file as UTF-8. Without it a
    # student named "Zoë" arrives as "ZoÃ«" on a Windows machine, which is the
    # kind of detail that makes a teacher distrust the whole export.
    return buffer.getvalue().encode("utf-8-sig")
