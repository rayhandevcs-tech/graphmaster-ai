"""Shared response shapes."""

from __future__ import annotations

from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

PageNumber = Annotated[int, Field(ge=1, description="1-indexed page number")]
PageSize = Annotated[int, Field(ge=1, le=100, description="Items per page, max 100")]


class ORMModel(BaseModel):
    """Base for models read from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """The collection envelope from docs/architecture/04-api-design.md §5.1."""

    items: list[T]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def build(cls, items: list[T], *, page: int, page_size: int, total: int) -> Page[T]:
        # Ceiling division without importing math; a zero-item result is still
        # one (empty) page, so clients never see total_pages = 0 with page = 1.
        total_pages = max(1, -(-total // page_size)) if page_size else 1
        return cls(
            items=items, page=page, page_size=page_size, total=total, total_pages=total_pages
        )


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """The error envelope from docs/architecture/04-api-design.md §5.2."""

    error: ErrorDetail


class MessageResponse(BaseModel):
    """A plain acknowledgement for endpoints with nothing to return."""

    message: str
