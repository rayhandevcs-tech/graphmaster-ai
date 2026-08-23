"""Vocabulary library endpoints (FR-6.x).

Reading is open to every authenticated user — students need the term list to
see what they are being scored against. Writing is teacher and administrator
only (FR-6.4).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, TeacherUser, VocabItemRepo, VocabularySvc
from app.schemas.common import Page
from app.schemas.vocabulary import (
    VocabularyBulkCreateRequest,
    VocabularyBulkResult,
    VocabularyCategoryOut,
    VocabularyItemCreate,
    VocabularyItemOut,
    VocabularyItemUpdate,
    VocabularySkipped,
)
from app.services.vocabulary import serialize_item

router = APIRouter(tags=["vocabulary"])


@router.get(
    "/categories",
    response_model=list[VocabularyCategoryOut],
    summary="The vocabulary categories",
)
async def list_categories(_: CurrentUser, vocabulary: VocabularySvc) -> list[VocabularyCategoryOut]:
    return [VocabularyCategoryOut.model_validate(c) for c in await vocabulary.list_categories()]


@router.get(
    "/items",
    response_model=Page[VocabularyItemOut],
    summary="Vocabulary terms",
)
async def list_items(
    _: CurrentUser,
    repo: VocabItemRepo,
    category: str | None = Query(default=None, max_length=32, description="Category code"),
    is_active: bool | None = Query(
        default=True,
        description="Defaults to active terms only; pass false to review deactivated ones.",
    ),
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> Page[VocabularyItemOut]:
    stmt = repo.build_list_query(category_code=category, is_active=is_active, search=search)
    rows, total = await repo.paginate(stmt, page=page, page_size=page_size)
    return Page[VocabularyItemOut].build(
        [VocabularyItemOut.model_validate(serialize_item(r)) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/items/{item_id}", response_model=VocabularyItemOut, summary="One term")
async def get_item(
    item_id: uuid.UUID, _: CurrentUser, vocabulary: VocabularySvc
) -> VocabularyItemOut:
    return VocabularyItemOut.model_validate(serialize_item(await vocabulary.get_item(item_id)))


# ── Teacher management ───────────────────────────────────────────────────────


@router.post(
    "/items",
    response_model=VocabularyItemOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a term (teachers and administrators)",
)
async def create_item(
    payload: VocabularyItemCreate, teacher: TeacherUser, vocabulary: VocabularySvc
) -> VocabularyItemOut:
    item = await vocabulary.create_item(payload, author=teacher)
    return VocabularyItemOut.model_validate(serialize_item(item))


@router.post(
    "/items/bulk",
    response_model=VocabularyBulkResult,
    status_code=status.HTTP_201_CREATED,
    summary="Import many terms at once (teachers and administrators)",
)
async def bulk_create_items(
    payload: VocabularyBulkCreateRequest, teacher: TeacherUser, vocabulary: VocabularySvc
) -> VocabularyBulkResult:
    created, skipped = await vocabulary.bulk_create(payload.items, author=teacher)
    return VocabularyBulkResult(
        created=[VocabularyItemOut.model_validate(serialize_item(i)) for i in created],
        skipped=[VocabularySkipped(**s) for s in skipped],
        created_count=len(created),
        skipped_count=len(skipped),
    )


@router.patch(
    "/items/{item_id}",
    response_model=VocabularyItemOut,
    summary="Edit a term (teachers and administrators)",
)
async def update_item(
    item_id: uuid.UUID,
    payload: VocabularyItemUpdate,
    _: TeacherUser,
    vocabulary: VocabularySvc,
) -> VocabularyItemOut:
    item = await vocabulary.update_item(item_id, payload)
    return VocabularyItemOut.model_validate(serialize_item(item))


@router.delete(
    "/items/{item_id}",
    response_model=VocabularyItemOut,
    summary="Deactivate a term (teachers and administrators)",
    description=(
        "Soft delete. The term stops being detected and can no longer be targeted, "
        "but the row survives so historical scores that reference it stay readable. "
        "Reactivate with PATCH `is_active: true`."
    ),
)
async def deactivate_item(
    item_id: uuid.UUID, _: TeacherUser, vocabulary: VocabularySvc
) -> VocabularyItemOut:
    item = await vocabulary.deactivate_item(item_id)
    return VocabularyItemOut.model_validate(serialize_item(item))
