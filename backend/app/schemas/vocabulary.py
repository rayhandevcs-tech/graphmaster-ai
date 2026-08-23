"""Vocabulary library schemas.

The library is teacher-editable (FR-6.4), so these carry the validation that
keeps a hand-entered term usable by the analyser: the ``lemma`` is the key
detection matches against, and a malformed one silently stops the term from
ever being detected.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


def normalize_lemma(value: str) -> str:
    """Lowercase, trim, and collapse internal whitespace.

    Detection compares against this string exactly, so "Bottom  Out" and
    "bottom out" must not become two rows that can never both match.
    """
    return " ".join(value.strip().lower().split())


def normalize_term(value: str) -> str:
    return " ".join(value.strip().split())


TermStr = Annotated[str, Field(min_length=1, max_length=100)]
# Numeric(3, 2) in the schema, so 9.99 is the widest value that round-trips.
Weight = Annotated[float, Field(gt=0, le=9.99)]


class VocabularyCategoryOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    display_order: int
    item_count: int = Field(default=0, description="Active terms in this category")


class VocabularyItemOut(ORMModel):
    id: uuid.UUID
    term: str
    lemma: str
    is_phrase: bool
    weight: float
    is_active: bool
    category_id: uuid.UUID
    category_code: str
    category_name: str
    created_at: datetime
    updated_at: datetime


class VocabularyItemCreate(BaseModel):
    """A new term.

    ``is_phrase`` is deliberately absent: it is derived from whether the term
    contains whitespace, so the flag can never disagree with the term itself.
    ``lemma`` defaults to the lowercased term, which is correct for the common
    single-word case; a teacher adding an irregular form ("higher than" →
    "high than") supplies it explicitly.
    """

    category_code: Annotated[str, Field(min_length=1, max_length=32)]
    term: TermStr
    lemma: TermStr | None = None
    weight: Weight = 1.0

    @field_validator("term")
    @classmethod
    def _clean_term(cls, v: str) -> str:
        cleaned = normalize_term(v)
        if not cleaned:
            raise ValueError("Term cannot be blank.")
        return cleaned

    @field_validator("lemma")
    @classmethod
    def _clean_lemma(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = normalize_lemma(v)
        if not cleaned:
            raise ValueError("Lemma cannot be blank.")
        return cleaned

    @field_validator("category_code")
    @classmethod
    def _clean_category(cls, v: str) -> str:
        return v.strip().lower()

    def resolved_lemma(self) -> str:
        return self.lemma or normalize_lemma(self.term)

    def resolved_is_phrase(self) -> bool:
        return " " in self.term


class VocabularyItemUpdate(BaseModel):
    """A partial update. Every field is optional; omitted fields are untouched.

    ``is_active`` is settable here so a soft-deleted term can be restored;
    ``DELETE`` only ever sets it false.
    """

    category_code: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    term: TermStr | None = None
    lemma: TermStr | None = None
    weight: Weight | None = None
    is_active: bool | None = None

    @field_validator("term")
    @classmethod
    def _clean_term(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = normalize_term(v)
        if not cleaned:
            raise ValueError("Term cannot be blank.")
        return cleaned

    @field_validator("lemma")
    @classmethod
    def _clean_lemma(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = normalize_lemma(v)
        if not cleaned:
            raise ValueError("Lemma cannot be blank.")
        return cleaned

    @field_validator("category_code")
    @classmethod
    def _clean_category(cls, v: str | None) -> str | None:
        return v.strip().lower() if v is not None else None


class VocabularyBulkCreateRequest(BaseModel):
    items: Annotated[list[VocabularyItemCreate], Field(min_length=1, max_length=200)]


class VocabularySkipped(BaseModel):
    term: str
    reason: str


class VocabularyBulkResult(BaseModel):
    """The outcome of a bulk import.

    Duplicates are skipped rather than failing the whole request: a teacher
    pasting forty terms where three already exist should not lose the other
    thirty-seven.
    """

    created: list[VocabularyItemOut]
    skipped: list[VocabularySkipped]
    created_count: int
    skipped_count: int
