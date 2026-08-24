"""Generating, storing and serving CSV / Excel / PDF exports (FR-11.5).

Generation is synchronous — the ``JobRunner`` seam in
``docs/architecture/05-backend-architecture.md`` §5 is where a queue would
attach — but the record is written the way an asynchronous run would leave it:
``pending`` first, then ``ready`` with a file, or ``failed`` with a reason. A
teacher whose 40,000-row export fell over gets a row telling them so instead of
a bare 500 and no trace.

Files are streamed back through an authenticated endpoint, never a static path.
An export names students, their scores and their email addresses; a guessable
URL for that would be a data breach with extra steps.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, BinaryIO

from sqlalchemy import Select

from app.core.config import Settings, get_settings
from app.core.exceptions import ReportNotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.enums import ReportFormat, ReportStatus, ReportType
from app.models.identity import User
from app.models.reporting import TeacherReport
from app.reports import CONTENT_TYPES, EXTENSIONS, builders, render
from app.repositories.analytics import AnalyticsRepository, AnalyticsWindow
from app.repositories.report import ReportRepository
from app.repositories.user import UserRepository
from app.services.analytics import AnalyticsService
from app.storage.base import StorageBackend

logger = get_logger(__name__)

# A hard ceiling on the raw export. Past this the file stops being something a
# teacher opens and becomes something that exhausts the server's memory while
# they wait; the date filters are the answer, and the note on the report says so.
MAX_EXPORT_ROWS = 20_000

STORAGE_PREFIX = "reports"


class ReportService:
    def __init__(
        self,
        analytics_service: AnalyticsService,
        analytics: AnalyticsRepository,
        reports: ReportRepository,
        users: UserRepository,
        storage: StorageBackend,
        settings: Settings | None = None,
    ) -> None:
        self.analytics_service = analytics_service
        self.analytics = analytics
        self.reports = reports
        self.users = users
        self.storage = storage
        self.settings = settings or get_settings()

    # ── Generating ───────────────────────────────────────────────────────────

    async def create(
        self,
        *,
        teacher: User,
        report_type: ReportType,
        fmt: ReportFormat,
        class_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        date_from: Any = None,
        date_to: Any = None,
    ) -> TeacherReport:
        """Build one report and store it.

        The access check runs through :class:`AnalyticsService`, so an export
        can never reach data the equivalent screen would refuse — a report is
        the easiest place to leak a class a teacher does not own, precisely
        because nobody looks at a CSV the way they look at a page.
        """
        parameters = {
            "class_id": str(class_id) if class_id else None,
            "student_id": str(student_id) if student_id else None,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        }
        report = TeacherReport(
            teacher_id=teacher.id,
            class_id=class_id,
            report_type=report_type.value,
            format=fmt.value,
            parameters=parameters,
            status=ReportStatus.PENDING.value,
        )
        await self.reports.add(report)

        try:
            document = await self._build(
                report_type,
                teacher=teacher,
                class_id=class_id,
                student_id=student_id,
                date_from=date_from,
                date_to=date_to,
            )
            payload = render(document, fmt)
        except Exception as exc:
            await self._record_failure(report, exc)
            raise

        stored = self.storage.save(
            payload,
            key=f"{STORAGE_PREFIX}/{report.id}.{EXTENSIONS[fmt]}",
            content_type=CONTENT_TYPES[fmt],
        )
        report.file_path = stored.key
        report.status = ReportStatus.READY.value
        report.completed_at = datetime.now(UTC)
        report.error_message = None
        await self.reports.db.flush()

        logger.info(
            "Report %s (%s/%s, %d bytes) generated for %s",
            report.id,
            report_type.value,
            fmt.value,
            stored.size,
            teacher.id,
        )
        return report

    async def _record_failure(self, report: TeacherReport, exc: Exception) -> None:
        """Persist the failure, then let the error propagate.

        The same deliberate commit as a failed handwriting extraction, and for
        the same reason: the request-scoped session rolls back on any
        exception, so a ``failed`` status written the ordinary way would be
        erased by the very error reporting it. Only this report's own columns
        are pending here, so the commit cannot carry out an unrelated
        half-finished write.
        """
        report.status = ReportStatus.FAILED.value
        report.error_message = str(exc)[:500]
        report.completed_at = datetime.now(UTC)
        await self.reports.db.commit()
        logger.error("Report %s failed: %s", report.id, exc)

    async def _build(
        self,
        report_type: ReportType,
        *,
        teacher: User,
        class_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        date_from: Any,
        date_to: Any,
    ):
        tz = self.settings.PLATFORM_TIMEZONE
        meta = await self._meta(
            teacher=teacher,
            class_id=class_id,
            student_id=student_id,
            date_from=date_from,
            date_to=date_to,
        )

        if report_type is ReportType.VOCABULARY_USAGE:
            data = await self.analytics_service.vocabulary_usage(
                viewer=teacher,
                class_id=class_id,
                date_from=date_from,
                date_to=date_to,
                # The export is read in full rather than skimmed, so it carries
                # the whole library instead of the screen's top ten.
                limit=MAX_EXPORT_ROWS,
            )
            return builders.vocabulary_usage(data, meta=meta, timezone=tz)

        if report_type is ReportType.SUBMISSION_EXPORT:
            window = await self._authorised_window(
                teacher=teacher,
                class_id=class_id,
                student_id=student_id,
                date_from=date_from,
                date_to=date_to,
            )
            rows = await self.analytics.submission_rows(
                window,
                timezone=self.settings.PLATFORM_TIMEZONE,
                limit=MAX_EXPORT_ROWS,
            )
            return builders.submission_export(rows, meta=meta, timezone=tz)

        if report_type is ReportType.STUDENT_DETAIL:
            if student_id is None:
                raise ValidationError("A student report needs `student_id`.")
            window = await self._authorised_window(
                teacher=teacher,
                class_id=class_id,
                student_id=student_id,
                date_from=date_from,
                date_to=date_to,
            )
            data = {
                **await self.analytics.overview(window, timezone=self.settings.PLATFORM_TIMEZONE),
                "engagement": await self.analytics.engagement(
                    window, timezone=self.settings.PLATFORM_TIMEZONE
                ),
                "trend": await self.analytics.trend(
                    window, timezone=self.settings.PLATFORM_TIMEZONE
                ),
                "students": await self.analytics.student_rows(
                    window, timezone=self.settings.PLATFORM_TIMEZONE
                ),
            }
            rows = await self.analytics.submission_rows(
                window, timezone=self.settings.PLATFORM_TIMEZONE, limit=MAX_EXPORT_ROWS
            )
            return builders.student_detail(data, submissions=rows, meta=meta, timezone=tz)

        if class_id is not None:
            data = await self.analytics_service.class_report(
                class_id, viewer=teacher, date_from=date_from, date_to=date_to
            )
        elif teacher.is_admin:
            data = await self.analytics_service.platform_report(
                date_from=date_from, date_to=date_to
            )
        else:
            raise ValidationError(
                "A class summary needs `class_id`. Only administrators can export "
                "across every class."
            )
        return builders.class_summary(data, meta=meta, timezone=tz)

    async def _authorised_window(
        self,
        *,
        teacher: User,
        class_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        date_from: Any,
        date_to: Any,
    ) -> AnalyticsWindow:
        """Narrow an export to what the caller may read.

        A teacher who names neither a class nor a student is scoped to their
        own classes rather than to the platform — the report equivalent of the
        submission listing's visibility rule, and the reason an unqualified
        export is safe to allow at all.
        """
        if class_id is not None:
            await self.analytics_service.require_class(class_id, teacher)
        if student_id is not None:
            await self._require_student(student_id, teacher)
        if class_id is None and student_id is None and not teacher.is_admin:
            raise ValidationError(
                "Name a class or a student to export. Only administrators can "
                "export across every class."
            )
        return AnalyticsWindow(
            class_id=class_id,
            student_id=student_id,
            date_from=date_from,
            date_to=date_to,
        )

    async def _require_student(self, student_id: uuid.UUID, teacher: User) -> User:
        student = await self.users.get(student_id)
        if student is None:
            raise ValidationError("That student does not exist.")
        if teacher.is_admin:
            return student
        if not await self.reports.teaches(teacher_id=teacher.id, student_id=student_id):
            # Reported as a validation failure rather than 403 for the same
            # reason the submission endpoints report a stranger's id as
            # missing: a distinct error would confirm the student exists.
            raise ValidationError("That student is not in one of your classes.")
        return student

    async def _meta(
        self,
        *,
        teacher: User,
        class_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        date_from: Any,
        date_to: Any,
    ) -> dict[str, str]:
        """The header block. Nobody should have to guess a report's scope."""
        meta = {"Prepared for": teacher.full_name}
        if class_id is not None:
            class_ = await self.analytics_service.classes.get(class_id)
            meta["Class"] = class_.name if class_ else str(class_id)
        if student_id is not None:
            student = await self.users.get(student_id)
            meta["Student"] = student.full_name if student else str(student_id)
        meta["Period"] = (
            f"{date_from or 'start'} to {date_to or 'today'}"
            if (date_from or date_to)
            else "All time"
        )
        meta["Timezone"] = self.settings.PLATFORM_TIMEZONE
        return meta

    # ── Reading ──────────────────────────────────────────────────────────────

    def build_list_query(self, teacher: User) -> Select[Any]:
        return self.reports.build_list_query(teacher)

    async def page(
        self, stmt: Select[Any], *, page: int, page_size: int
    ) -> tuple[list[TeacherReport], int]:
        return await self.reports.paginate(stmt, page=page, page_size=page_size)

    async def get_for(self, report_id: uuid.UUID, *, viewer: User) -> TeacherReport:
        report = await self.reports.get(report_id)
        if report is None:
            raise ReportNotFoundError()
        if not viewer.is_admin and report.teacher_id != viewer.id:
            # Someone else's export is reported as absent, not forbidden: a 403
            # would confirm that a guessed id names a real report.
            raise ReportNotFoundError()
        return report

    async def download(self, report_id: uuid.UUID, *, viewer: User) -> tuple[BinaryIO, str, str]:
        """Open a finished report for streaming, with its type and filename."""
        report = await self.get_for(report_id, viewer=viewer)
        if report.status != ReportStatus.READY.value or not report.file_path:
            raise ReportNotFoundError(
                f"This report is {report.status} and has no file to download."
            )

        try:
            stream = self.storage.open(report.file_path)
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Report %s file missing: %s", report_id, report.file_path)
            raise ReportNotFoundError("The generated file is no longer available.") from exc

        fmt = ReportFormat(report.format)
        stamp = report.created_at.strftime("%Y%m%d-%H%M")
        filename = f"graphmaster-{report.report_type}-{stamp}.{EXTENSIONS[fmt]}"
        return stream, CONTENT_TYPES[fmt], filename

    async def delete(self, report_id: uuid.UUID, *, viewer: User) -> None:
        """Remove a report and the file behind it."""
        report = await self.get_for(report_id, viewer=viewer)
        key = report.file_path
        await self.reports.delete(report)
        if key:
            # After the row, and only after: a file deleted first would be gone
            # even if the transaction then rolled the row back, leaving a
            # report the teacher can see and cannot download.
            self.storage.delete(key)
        logger.info("Report %s deleted by %s", report_id, viewer.id)
