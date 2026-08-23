"""Domain exception hierarchy.

Services raise these, never ``HTTPException``. A single handler registered in
``app.main`` maps them to the error envelope defined in
``docs/architecture/04-api-design.md`` §5.2, so the domain-to-HTTP mapping
exists in exactly one place and services stay callable outside a request.
"""

from __future__ import annotations

from typing import Any


class GraphMasterError(Exception):
    """Base for every domain error."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


# ── 404 ──────────────────────────────────────────────────────────────────────


class NotFoundError(GraphMasterError):
    status_code = 404
    code = "NOT_FOUND"
    message = "The requested resource was not found."


class UserNotFoundError(NotFoundError):
    code = "USER_NOT_FOUND"
    message = "User not found."


class GraphNotFoundError(NotFoundError):
    code = "GRAPH_NOT_FOUND"
    message = "Graph not found."


class SubmissionNotFoundError(NotFoundError):
    code = "SUBMISSION_NOT_FOUND"
    message = "Submission not found, or you do not have access to it."


class ClassNotFoundError(NotFoundError):
    code = "CLASS_NOT_FOUND"
    message = "Class not found."


class VocabularyItemNotFoundError(NotFoundError):
    code = "VOCABULARY_ITEM_NOT_FOUND"
    message = "Vocabulary item not found."


class AvatarNotFoundError(NotFoundError):
    code = "AVATAR_NOT_FOUND"
    message = "Avatar not found."


class ReportNotFoundError(NotFoundError):
    code = "REPORT_NOT_FOUND"
    message = "Report not found."


class ClassCodeInvalidError(NotFoundError):
    code = "CLASS_CODE_INVALID"
    message = "That class code is not valid."


# ── 401 ──────────────────────────────────────────────────────────────────────


class AuthenticationError(GraphMasterError):
    status_code = 401
    code = "AUTHENTICATION_FAILED"
    message = "Authentication failed."


class InvalidCredentialsError(AuthenticationError):
    code = "INVALID_CREDENTIALS"
    message = "Incorrect email or password."


class TokenExpiredError(AuthenticationError):
    code = "TOKEN_EXPIRED"
    message = "Your session has expired. Please sign in again."


class InvalidTokenError(AuthenticationError):
    code = "INVALID_TOKEN"
    message = "Invalid authentication token."


class AccountInactiveError(AuthenticationError):
    code = "ACCOUNT_INACTIVE"
    message = "This account has been deactivated."


# ── 403 ──────────────────────────────────────────────────────────────────────


class PermissionDeniedError(GraphMasterError):
    status_code = 403
    code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action."


class InsufficientRoleError(PermissionDeniedError):
    code = "INSUFFICIENT_ROLE"
    message = "Your role does not permit this action."


# ── 409 ──────────────────────────────────────────────────────────────────────


class ConflictError(GraphMasterError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with the current state of the resource."


class EmailAlreadyRegisteredError(ConflictError):
    code = "EMAIL_ALREADY_REGISTERED"
    message = "An account with this email already exists."


class SubmissionAlreadyScoredError(ConflictError):
    code = "SUBMISSION_ALREADY_SCORED"
    message = "This submission has already been scored."


class SubmissionNotReadyError(ConflictError):
    code = "SUBMISSION_NOT_READY"
    message = "This submission has no answer text to analyse yet."


class GraphHasSubmissionsError(ConflictError):
    code = "GRAPH_HAS_SUBMISSIONS"
    message = "This graph cannot be deleted because students have already attempted it."


class NoTargetVocabularyError(ConflictError):
    code = "NO_TARGET_VOCABULARY"
    message = "This graph has no target vocabulary configured."


class DuplicateVocabularyTermError(ConflictError):
    code = "DUPLICATE_VOCABULARY_TERM"
    message = "That vocabulary term already exists."


# ── 413 / 415 / 422 ──────────────────────────────────────────────────────────


class FileTooLargeError(GraphMasterError):
    status_code = 413
    code = "FILE_TOO_LARGE"
    message = "The uploaded file is too large."


class UnsupportedFileTypeError(GraphMasterError):
    status_code = 415
    code = "UNSUPPORTED_FILE_TYPE"
    message = "Only JPG, JPEG, PNG and WEBP images are accepted."


class ValidationError(GraphMasterError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "The request could not be processed."


class OCRError(ValidationError):
    code = "OCR_FAILED"
    message = "Text could not be extracted from the image."


class AnalysisError(ValidationError):
    code = "ANALYSIS_FAILED"
    message = "The response could not be analysed."


# ── 429 ──────────────────────────────────────────────────────────────────────


class RateLimitError(GraphMasterError):
    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests. Please wait and try again."

    def __init__(self, retry_after: int = 60, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.retry_after = retry_after
