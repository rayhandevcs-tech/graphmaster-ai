"""The practice flow: open an attempt, get text into it, score it.

One submission moves through the state machine in
``docs/architecture/02-database-schema.md`` §3.6:

    draft ──(upload)──> extracting ──> extracted ──┐
      │                     └────────> failed ─────┤
      │                                            │
      └────────────(set text)──────────────────────┴──> analyzing ──> scored

``extracting``/``extracted``/``failed`` belong to the handwriting route only;
a typed answer goes straight from ``draft`` to ``analyzing``. ``failed`` is
recoverable by design — the uploaded page is retained, so the student can try
another photograph or simply type what they wrote (FR-4.9).

Two properties this module is responsible for:

* **Scoring happens at most once per submission.** The row is locked before the
  status is read, so two concurrent ``analyze`` calls cannot both produce a
  score, and cannot both award XP for one piece of work.
* **A recognition failure survives the error that reports it.** See
  :meth:`SubmissionService._record_extraction_failure`.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any, BinaryIO

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    OCRError,
    OCRUnreadableError,
    ServiceUnavailableError,
    SubmissionAlreadyScoredError,
    SubmissionNotFoundError,
    SubmissionNotReadyError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models.content import Assignment, Graph
from app.models.enums import InputMethod, SubmissionStatus
from app.models.identity import User
from app.models.submission import Score, Submission
from app.nlp.analyzer import AnalysisResult
from app.ocr.postprocess import word_count as count_words
from app.repositories.assessment import AssessmentRepository
from app.repositories.submission import SubmissionRepository
from app.services.analysis import AnalysisService
from app.services.assignment import AssignmentService
from app.services.gamification import AwardResult, GamificationService
from app.services.graph import GraphService
from app.services.ocr import OCRService

logger = get_logger(__name__)

# Statuses from which the answer text may still be set or corrected. `failed`
# is included deliberately: a student whose photograph could not be read must
# be able to type the answer into the same attempt rather than start again.
EDITABLE_STATUSES = frozenset(
    {
        SubmissionStatus.DRAFT.value,
        SubmissionStatus.EXTRACTED.value,
        SubmissionStatus.FAILED.value,
    }
)

CONTENT_TYPE_FOR_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_WHITESPACE = re.compile(r"\s+")


class SubmissionService:
    def __init__(
        self,
        submissions: SubmissionRepository,
        graph_service: GraphService,
        analysis: AnalysisService,
        ocr: OCRService,
        gamification: GamificationService,
        assessments: AssessmentRepository,
        assignments: AssignmentService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.submissions = submissions
        self.graph_service = graph_service
        self.analysis = analysis
        self.ocr = ocr
        self.gamification = gamification
        self.assessments = assessments
        # Optional because free practice is the core loop and needs none of
        # it: a service constructed without assignments still opens, scores
        # and awards exactly as it did before they existed.
        self.assignments = assignments
        self.settings = settings or get_settings()

    # ── Opening an attempt ───────────────────────────────────────────────────

    async def start(
        self,
        *,
        graph_id: uuid.UUID,
        input_method: InputMethod,
        student: User,
        assignment_id: uuid.UUID | None = None,
    ) -> Submission:
        """Open a submission against a graph.

        The graph is resolved through the graph service, so an unpublished
        draft reads as absent to a student and cannot be attempted.

        ``assignment_id`` only *labels* the attempt. A student who picked the
        graph out of the library passes none, and every later step — scoring,
        the tier, the XP award, the leaderboard — reads the same either way.
        """
        graph = await self.graph_service.get_for(graph_id, viewer=student)
        assignment_id = await self._resolve_assignment(assignment_id, graph_id, student)

        existing = await self.submissions.reusable_draft(
            user_id=student.id,
            graph_id=graph.id,
            input_method=input_method,
            assignment_id=assignment_id,
        )
        if existing is not None:
            logger.debug("Reusing pristine draft %s for %s", existing.id, student.id)
            return await self._reload(existing.id)

        submission = Submission(
            user_id=student.id,
            graph_id=graph.id,
            assignment_id=assignment_id,
            input_method=input_method.value,
            status=SubmissionStatus.DRAFT.value,
            word_count=0,
        )
        await self.submissions.add(submission)
        logger.info(
            "Submission %s opened by %s on graph %s (%s)",
            submission.id,
            student.id,
            graph.id,
            input_method.value,
        )
        return await self._reload(submission.id)

    async def _resolve_assignment(
        self, assignment_id: uuid.UUID | None, graph_id: uuid.UUID, student: User
    ) -> uuid.UUID | None:
        """Check the claimed assignment, or return None for free practice.

        A student can name any assignment id in a request body, so it is
        checked rather than trusted: work set for a class they are not in
        reads as absent, and an assignment pointing at a different graph is
        refused outright — accepting it would file this answer against a
        question nobody asked.
        """
        if assignment_id is None or self.assignments is None:
            return None
        assignment = await self.assignments.require_open_for(assignment_id, student=student)
        if assignment.graph_id != graph_id:
            raise ValidationError("That assignment is set on a different graph.")
        return assignment.id

    # ── Handwriting ──────────────────────────────────────────────────────────

    async def upload(
        self, submission_id: uuid.UUID, data: bytes, *, filename: str | None, student: User
    ) -> tuple[Submission, str | None]:
        """Recognise a photograph of handwriting into this submission.

        The extracted text becomes ``answer_text`` **and** is preserved
        untouched as ``ocr_text``. The pair is what makes recognition accuracy
        measurable afterwards rather than merely visible as a low score.

        Returns the submission with the recogniser's warning, if it raised one.
        The warning is advice about *this reading* rather than state of the
        submission, so it rides the response instead of being persisted.
        """
        submission = await self._require_editable(submission_id, student)

        if submission.input_method != InputMethod.HANDWRITING.value:
            raise ValidationError(
                "This is a typed submission, so there is no image to read. "
                "Start a handwriting submission to upload a photograph."
            )
        if not self.ocr.is_operational:
            raise ServiceUnavailableError(
                "No handwriting recognition engine is configured on this server. "
                "Type your answer instead."
            )

        submission.status = SubmissionStatus.EXTRACTING.value
        submission.error_message = None
        await self.submissions.db.flush()

        try:
            outcome = self.ocr.extract(data, filename=filename)
        except OCRError as exc:
            await self._record_extraction_failure(submission, exc)
            raise

        submission.ocr_text = outcome.text
        submission.answer_text = outcome.text
        submission.ocr_provider = outcome.provider
        submission.ocr_confidence = outcome.confidence
        submission.ocr_blocks = outcome.blocks
        submission.was_ocr_edited = False
        submission.original_image_path = outcome.storage_key
        submission.word_count = outcome.word_count
        submission.status = SubmissionStatus.EXTRACTED.value
        submission.error_message = None

        await self.submissions.db.flush()
        logger.info(
            "Submission %s extracted by %s (%d words, confidence %s)",
            submission.id,
            outcome.provider,
            outcome.word_count,
            outcome.confidence,
        )
        return await self._reload(submission.id), outcome.warning

    async def _record_extraction_failure(self, submission: Submission, exc: OCRError) -> None:
        """Persist the failure, then let the error propagate.

        This is the one place in the application where a service commits. It
        has to: the request-scoped session rolls back on any exception, so a
        ``failed`` status written the ordinary way would be erased by the very
        error that is reporting it, and the submission would be handed back to
        the student still sitting in ``extracting`` with no record of what went
        wrong. Committing here is what makes ``failed`` a state the schema
        actually reaches.

        Only this submission's own columns are pending at this point, so the
        commit cannot smuggle out an unrelated half-finished write.
        """
        submission.status = SubmissionStatus.FAILED.value
        submission.error_message = exc.message
        if isinstance(exc, OCRUnreadableError) and exc.storage_key:
            # Recorded even though recognition failed: the image is retained,
            # and without its path no endpoint could ever show it back.
            submission.original_image_path = exc.storage_key

        await self.submissions.db.commit()
        logger.warning("Submission %s failed extraction: %s", submission.id, exc.message)

    # ── Text ─────────────────────────────────────────────────────────────────

    async def set_text(self, submission_id: uuid.UUID, text: str, *, student: User) -> Submission:
        """Set or correct the answer text before analysis (FR-4.7)."""
        submission = await self._require_editable(submission_id, student)

        cleaned = text.strip()
        if not cleaned:
            raise ValidationError("The answer cannot be empty.")

        submission.answer_text = cleaned
        submission.word_count = count_words(cleaned)

        # Only a *reading* can be corrected. When recognition returned nothing —
        # a blank or unreadable page, which Sprint 4 treats as a legitimate
        # outcome rather than an error — the student is typing from scratch,
        # not fixing the machine. Counting that as an edit would conflate
        # "recognition failed" with "recognition was inaccurate", which are
        # different findings about the OCR chain.
        if submission.ocr_text and submission.ocr_text.strip():
            submission.was_ocr_edited = _differs(cleaned, submission.ocr_text)

        # A student typing into a failed handwriting attempt is recovering from
        # it, so the attempt is no longer failed. `input_method` deliberately
        # stays `handwriting`: the research record should show that handwriting
        # was attempted and that recognition did not work, not that this was a
        # typed answer all along.
        if submission.status == SubmissionStatus.FAILED.value:
            submission.status = SubmissionStatus.DRAFT.value
            submission.error_message = None

        await self.submissions.db.flush()
        return await self._reload(submission.id)

    # ── Analysis ─────────────────────────────────────────────────────────────

    async def analyse(
        self, submission_id: uuid.UUID, *, student: User
    ) -> tuple[Submission, AnalysisResult, AwardResult]:
        """Score the submission, award what it earns, and persist both.

        The row is locked before its status is read. Two ``analyze`` requests
        racing on one submission therefore serialise: the first scores it, and
        the second — which waits on the lock rather than reading stale state —
        finds it already scored and is refused. That lock is what makes the XP
        award safe as well as the score: without it both callers would run the
        engine and both would pay out for one piece of work.

        Scoring and awarding share this one transaction. Committing them
        separately would leave a window in which a student has a score and no
        XP, which reads as the system having lost their work.
        """
        locked = await self.submissions.lock(submission_id)
        if locked is None or locked.user_id != student.id:
            # An id belonging to someone else is reported as missing rather
            # than forbidden, so the endpoint cannot confirm that a guessed
            # submission exists (04-api-design.md §5.2).
            raise SubmissionNotFoundError()
        if locked.status == SubmissionStatus.SCORED.value:
            raise SubmissionAlreadyScoredError()

        text = (locked.answer_text or "").strip()
        if not text:
            raise SubmissionNotReadyError(
                "Add your answer before submitting it for marking."
                if locked.input_method == InputMethod.TYPED.value
                else "Upload your handwriting or type your answer before submitting it."
            )

        graph = await self.graph_service.get_for(locked.graph_id, viewer=student)

        locked.status = SubmissionStatus.ANALYZING.value
        await self.submissions.db.flush()

        # A failure here — an unanalysable answer, or a server with no language
        # model — rolls the whole transaction back, including this status. That
        # is deliberate: both are retryable, and burning the student's attempt
        # on a deployment fault would destroy work they cannot recover.
        result = await self.analysis.analyse_for_graph(graph, text, student=student)

        score = Score(submission_id=locked.id, **result.to_score_fields())
        self.submissions.db.add(score)

        # The diagnostic record, in the same transaction as the score it
        # accompanies. `result.assessment` is None when the pass is switched
        # off, when no analyzer is configured, or when building it failed — all
        # three leave the submission scored and the student's work intact,
        # which is the whole reason it is a separate optional row rather than
        # columns on `scores`.
        if result.assessment is not None:
            await self.assessments.create_for(locked.id, result.assessment)

        locked.status = SubmissionStatus.SCORED.value
        locked.scored_at = datetime.now(UTC)
        # The engine's count replaces the provisional one: it counts what was
        # actually parsed and scored, so the number shown next to the word-count
        # component is the number that component was computed from.
        locked.word_count = result.word_count
        locked.error_message = None

        # Flushed before awarding, so the aggregates behind the achievement
        # rules count this submission. Without it "First Steps" would not
        # unlock until the student's *second* attempt.
        await self.submissions.db.flush()

        awards = await self.gamification.on_submission_scored(locked, score, student=student)

        await self.submissions.db.flush()
        logger.info(
            "Submission %s scored %.2f (%s) for %s",
            locked.id,
            result.score.final_score,
            result.score.reward_tier.value,
            student.id,
        )
        return await self._reload(locked.id), result, awards

    # ── Reads ────────────────────────────────────────────────────────────────

    async def get_for(self, submission_id: uuid.UUID, *, viewer: User) -> Submission:
        submission = await self.submissions.get_full(submission_id)
        if submission is None:
            raise SubmissionNotFoundError()
        if not await self.submissions.visible_to(submission, viewer):
            raise SubmissionNotFoundError()
        return submission

    async def image(self, submission_id: uuid.UUID, *, viewer: User) -> tuple[BinaryIO, str]:
        """Open the stored original for streaming, with its content type."""
        submission = await self.get_for(submission_id, viewer=viewer)
        key = submission.original_image_path
        if not key:
            raise SubmissionNotFoundError("This submission has no uploaded image.")

        try:
            stream = self.ocr.storage.open(key)
        except (FileNotFoundError, ValueError) as exc:
            # The row points at a file that is not there — a restored database
            # without its storage volume, usually. Reported as missing rather
            # than as a 500, because nothing is going to fix it by retrying.
            logger.error("Submission %s image missing from storage: %s", submission_id, key)
            raise SubmissionNotFoundError("The uploaded image is no longer available.") from exc

        suffix = key[key.rfind(".") :].lower() if "." in key else ""
        return stream, CONTENT_TYPE_FOR_EXTENSION.get(suffix, "application/octet-stream")

    async def discard(self, submission_id: uuid.UUID, *, student: User) -> None:
        """Delete an unscored attempt.

        A scored submission is never deletable: it carries XP that has already
        been awarded and counts towards achievements and the leaderboard, so
        removing it would leave the ledger describing work that no longer
        exists.
        """
        submission = await self.submissions.get_full(submission_id)
        if submission is None or submission.user_id != student.id:
            raise SubmissionNotFoundError()
        if submission.status == SubmissionStatus.SCORED.value:
            raise SubmissionAlreadyScoredError(
                "A scored submission is part of your history and cannot be discarded."
            )

        await self.submissions.delete(submission)
        logger.info("Submission %s discarded by %s", submission_id, student.id)

    # ── Serialisation ────────────────────────────────────────────────────────

    def detail_payload(self, submission: Submission, *, viewer: User) -> dict[str, Any]:
        graph: Graph | None = submission.graph
        # Eager-loaded by `get_full`; `None` both for free practice and for an
        # assignment that has since been deleted, which is the same thing to a
        # student reading their own history back.
        assignment: Assignment | None = submission.assignment
        payload: dict[str, Any] = {
            "id": submission.id,
            "graph_id": submission.graph_id,
            "graph_title": graph.title if graph else None,
            "graph_type": graph.graph_type if graph else None,
            "assignment_id": submission.assignment_id,
            "assignment_title": assignment.title if assignment else None,
            "user_id": submission.user_id,
            "student_name": submission.user.full_name if submission.user else None,
            "input_method": submission.input_method,
            "status": submission.status,
            "answer_text": submission.answer_text,
            "word_count": submission.word_count,
            "ocr_text": submission.ocr_text,
            "ocr_provider": submission.ocr_provider,
            "ocr_confidence": (
                float(submission.ocr_confidence) if submission.ocr_confidence is not None else None
            ),
            "was_ocr_edited": submission.was_ocr_edited,
            "has_image": bool(submission.original_image_path),
            "image_url": (
                f"{self.settings.API_V1_PREFIX}/submissions/{submission.id}/image"
                if submission.original_image_path
                else None
            ),
            "error_message": submission.error_message,
            "submitted_at": submission.submitted_at,
            "scored_at": submission.scored_at,
            "score": _score_payload(submission.score) if submission.score else None,
        }

        # The model answer is released once the attempt is scored, and to staff
        # at any time. Before that it is withheld for the same reason the graph
        # endpoints withhold it: it is the answer to the exercise in progress.
        if graph is not None and (
            viewer.can_manage_content or submission.status == SubmissionStatus.SCORED.value
        ):
            payload["reference_description"] = graph.reference_description

        return payload

    def summary_payload(self, submission: Submission) -> dict[str, Any]:
        graph: Graph | None = submission.graph
        score = submission.score
        return {
            "id": submission.id,
            "graph_id": submission.graph_id,
            "graph_title": graph.title if graph else None,
            "graph_type": graph.graph_type if graph else None,
            "user_id": submission.user_id,
            "student_name": submission.user.full_name if submission.user else None,
            "input_method": submission.input_method,
            "status": submission.status,
            "word_count": submission.word_count,
            "final_score": float(score.final_score) if score else None,
            "vocabulary_percentage": float(score.vocabulary_percentage) if score else None,
            "reward_tier": score.reward_tier if score else None,
            "submitted_at": submission.submitted_at,
            "scored_at": submission.scored_at,
        }

    # ── Internals ────────────────────────────────────────────────────────────

    async def _require_editable(self, submission_id: uuid.UUID, student: User) -> Submission:
        submission = await self.submissions.get_full(submission_id)
        if submission is None or submission.user_id != student.id:
            raise SubmissionNotFoundError()
        if submission.status == SubmissionStatus.SCORED.value:
            raise SubmissionAlreadyScoredError(
                "This attempt has been marked, so it can no longer be changed. "
                "Start the graph again for another attempt."
            )
        if submission.status not in EDITABLE_STATUSES:
            raise SubmissionNotReadyError(
                f"This submission is {submission.status} and cannot be changed right now."
            )
        return submission

    async def _reload(self, submission_id: uuid.UUID) -> Submission:
        """Re-read after a flush.

        ``updated_at``-style server defaults are expired by a flush, and a
        relationship populated by foreign key alone is stale in the identity
        map; both surface as a lazy load the async driver cannot service.
        """
        submission = await self.submissions.get_full(submission_id)
        if submission is None:  # pragma: no cover - the row was just written
            raise SubmissionNotFoundError()
        return submission


def _differs(text: str, original: str) -> bool:
    """Whether the student meaningfully changed the recognised text.

    Whitespace is collapsed before comparing, so a reflowed line break does not
    register as a correction. The flag exists to measure how often recognition
    needed fixing; counting cosmetic changes would inflate that figure and make
    the OCR look worse than it is.
    """
    return _WHITESPACE.sub(" ", text).strip() != _WHITESPACE.sub(" ", original).strip()


def _score_payload(score: Score) -> dict[str, Any]:
    return {
        "vocabulary_score": float(score.vocabulary_score),
        "writing_score": float(score.writing_score),
        "final_score": float(score.final_score),
        "vocabulary_percentage": float(score.vocabulary_percentage),
        "detected_count": score.detected_count,
        "unique_detected_count": score.unique_detected_count,
        "total_target_count": score.total_target_count,
        "detected_terms": score.detected_terms,
        "missing_terms": score.missing_terms,
        "category_breakdown": score.category_breakdown,
        "writing_breakdown": score.writing_breakdown,
        "reward_tier": score.reward_tier,
        "feedback": score.feedback,
        "engine_version": score.engine_version,
        "scored_at": score.created_at,
    }
