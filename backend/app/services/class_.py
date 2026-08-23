"""Class (cohort) business logic.

Access rule, from FR-11.6: a teacher may only act on classes they own; an
administrator is unrestricted. It is enforced in one place —
``_require_access`` — so no endpoint can forget it.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from app.core.exceptions import (
    ClassCodeInvalidError,
    ClassNotFoundError,
    ConflictError,
    PermissionDeniedError,
    UserNotFoundError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models.identity import Class, User
from app.repositories.class_ import ClassRepository
from app.repositories.user import UserRepository
from app.schemas.class_ import CODE_ALPHABET, CODE_LENGTH, ClassCreate, ClassUpdate

logger = get_logger(__name__)

# Enough attempts that a collision run is vanishingly unlikely, few enough
# that a genuinely exhausted keyspace fails fast instead of spinning.
CODE_ATTEMPTS = 12


class ClassService:
    def __init__(self, classes: ClassRepository, users: UserRepository) -> None:
        self.classes = classes
        self.users = users

    # ── Access control ───────────────────────────────────────────────────────

    def _require_access(self, class_: Class, actor: User) -> None:
        if actor.is_admin:
            return
        if class_.teacher_id != actor.id:
            raise PermissionDeniedError("You can only manage classes you teach.")

    async def _require_class(self, class_id: uuid.UUID) -> Class:
        class_ = await self.classes.get_with_teacher(class_id)
        if class_ is None:
            raise ClassNotFoundError()
        return class_

    async def get(self, class_id: uuid.UUID, *, actor: User) -> dict[str, Any]:
        class_ = await self._require_class(class_id)
        self._require_access(class_, actor)
        return await self.detail_payload(class_)

    # ── Serialisation ────────────────────────────────────────────────────────

    async def summaries(self, rows: list[Class]) -> list[dict[str, Any]]:
        counts = await self.classes.student_counts([c.id for c in rows])
        return [self._summary(c, counts.get(c.id, 0)) for c in rows]

    @staticmethod
    def _summary(class_: Class, student_count: int) -> dict[str, Any]:
        return {
            "id": class_.id,
            "name": class_.name,
            "code": class_.code,
            "description": class_.description,
            "teacher_id": class_.teacher_id,
            "is_active": class_.is_active,
            "student_count": student_count,
            "created_at": class_.created_at,
        }

    async def detail_payload(self, class_: Class) -> dict[str, Any]:
        count = await self.classes.student_count(class_.id)
        return self._summary(class_, count) | {
            "teacher_name": class_.teacher.full_name,
            "updated_at": class_.updated_at,
        }

    # ── Writes ───────────────────────────────────────────────────────────────

    async def create(self, payload: ClassCreate, *, teacher: User) -> dict[str, Any]:
        if payload.code is not None:
            if await self.classes.code_exists(payload.code):
                raise ConflictError(f"The join code {payload.code!r} is already in use.")
            code = payload.code
        else:
            code = await self._generate_code()

        class_ = Class(
            name=payload.name,
            code=code,
            description=payload.description,
            teacher_id=teacher.id,
            is_active=True,
        )
        await self.classes.add(class_)
        logger.info("Class %r (%s) created by %s", class_.name, code, teacher.id)
        return await self.detail_payload(await self._require_class(class_.id))

    async def _generate_code(self) -> str:
        """A random, unambiguous join code that is not already taken.

        ``secrets`` rather than ``random``: the code is the only thing standing
        between a stranger and a class roster, so it must not be predictable
        from another code issued nearby in time.
        """
        for _ in range(CODE_ATTEMPTS):
            candidate = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if not await self.classes.code_exists(candidate):
                return candidate
        raise ConflictError(  # pragma: no cover - needs ~31^8 existing codes
            "Could not allocate a unique join code. Please try again."
        )

    async def update(
        self, class_id: uuid.UUID, payload: ClassUpdate, *, actor: User
    ) -> dict[str, Any]:
        class_ = await self._require_class(class_id)
        self._require_access(class_, actor)

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(class_, field, value)

        await self.classes.db.flush()
        # Re-read rather than serialising the flushed instance: `updated_at`
        # has a server-side onupdate, so the flush expires it and reading it
        # back would trigger a lazy refresh in the middle of building the
        # response — which the async driver cannot service.
        return await self.detail_payload(await self._require_class(class_id))

    # ── Roster ───────────────────────────────────────────────────────────────

    async def roster(self, class_id: uuid.UUID, *, actor: User) -> list[User]:
        class_ = await self._require_class(class_id)
        self._require_access(class_, actor)
        return await self.users.list_by_class(class_id)

    async def enrol_by_email(self, class_id: uuid.UUID, email: str, *, actor: User) -> User:
        class_ = await self._require_class(class_id)
        self._require_access(class_, actor)

        student = await self.users.get_by_email(email)
        if student is None:
            raise UserNotFoundError("No account is registered with that email address.")
        if not student.is_student:
            raise ValidationError("Only students can be enrolled in a class.")
        if student.class_id == class_id:
            raise ConflictError("That student is already in this class.")

        student.class_id = class_id
        await self.users.db.flush()
        logger.info("Student %s enrolled in class %s by %s", student.id, class_id, actor.id)
        return student

    async def unenrol(self, class_id: uuid.UUID, user_id: uuid.UUID, *, actor: User) -> None:
        class_ = await self._require_class(class_id)
        self._require_access(class_, actor)

        student = await self.users.get(user_id)
        if student is None or student.class_id != class_id:
            # Reported against the class, not the user: a teacher has no
            # business learning whether an unrelated account exists.
            raise UserNotFoundError("That student is not in this class.")

        student.class_id = None
        await self.users.db.flush()
        logger.info("Student %s removed from class %s by %s", user_id, class_id, actor.id)

    async def join_by_code(self, code: str, *, student: User) -> dict[str, Any]:
        class_ = await self.classes.get_by_code(code)
        if class_ is None or not class_.is_active:
            # An inactive class is indistinguishable from a wrong code, so a
            # guessed code cannot confirm that a class exists.
            raise ClassCodeInvalidError("That join code is not valid.")

        student.class_id = class_.id
        await self.users.db.flush()
        logger.info("Student %s joined class %s by code", student.id, class_.id)
        return await self.detail_payload(class_)
