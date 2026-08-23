"""Vocabulary library business logic (FR-6.x).

Terms are never hard-deleted. Historical scores store the terms a submission
matched, so removing a row would make a student's past result unexplainable —
see CLAUDE.md rule 10 and docs/architecture/02-database-schema.md §3.4.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.exceptions import (
    DuplicateVocabularyTermError,
    ValidationError,
    VocabularyItemNotFoundError,
)
from app.core.logging import get_logger
from app.models.content import VocabularyCategory, VocabularyItem
from app.models.identity import User
from app.repositories.vocabulary import (
    VocabularyCategoryRepository,
    VocabularyItemRepository,
)
from app.schemas.vocabulary import (
    VocabularyItemCreate,
    VocabularyItemUpdate,
    normalize_lemma,
)

logger = get_logger(__name__)


def serialize_item(item: VocabularyItem) -> dict[str, Any]:
    """Flatten an item and its category into one response shape.

    Done here rather than with a nested schema so the client gets
    ``category_code`` directly — that is the key it filters and groups by, and
    a nested object would make every consumer reach through it.
    """
    return {
        "id": item.id,
        "term": item.term,
        "lemma": item.lemma,
        "is_phrase": item.is_phrase,
        "weight": float(item.weight),
        "is_active": item.is_active,
        "category_id": item.category_id,
        "category_code": item.category.code,
        "category_name": item.category.name,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


class VocabularyService:
    def __init__(
        self,
        categories: VocabularyCategoryRepository,
        items: VocabularyItemRepository,
    ) -> None:
        self.categories = categories
        self.items = items

    async def list_categories(self) -> list[dict[str, Any]]:
        rows = await self.categories.list_all()
        counts = await self.categories.active_item_counts()
        return [
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "description": c.description,
                "display_order": c.display_order,
                "item_count": counts.get(c.id, 0),
            }
            for c in rows
        ]

    async def _require_category(self, code: str) -> VocabularyCategory:
        category = await self.categories.get_by_code(code)
        if category is None:
            available = ", ".join(c.code for c in await self.categories.list_all())
            raise ValidationError(f"Unknown category {code!r}. Available: {available}.")
        return category

    async def create_item(self, payload: VocabularyItemCreate, *, author: User) -> VocabularyItem:
        category = await self._require_category(payload.category_code)
        lemma = payload.resolved_lemma()

        existing = await self.items.get_by_lemma(lemma)
        if existing is not None:
            # A soft-deleted term still owns its lemma, so say so explicitly
            # rather than reporting a plain conflict the teacher cannot see.
            state = "already exists" if existing.is_active else "exists but is deactivated"
            raise DuplicateVocabularyTermError(
                f"A term with lemma {lemma!r} {state} ({existing.term!r}). "
                "Reactivate or edit it instead of creating a duplicate."
            )

        item = VocabularyItem(
            category_id=category.id,
            term=payload.term,
            lemma=lemma,
            is_phrase=payload.resolved_is_phrase(),
            weight=payload.weight,
            is_active=True,
            created_by=author.id,
        )
        await self.items.add(item)
        logger.info("Vocabulary term %r created by %s", item.term, author.id)
        return await self._reload(item.id)

    async def bulk_create(
        self, payloads: list[VocabularyItemCreate], *, author: User
    ) -> tuple[list[VocabularyItem], list[dict[str, str]]]:
        """Import many terms at once, skipping the ones that clash.

        Returns ``(created, skipped)``. Duplicates do not fail the request —
        see ``VocabularyBulkResult``.
        """
        lemmas = [p.resolved_lemma() for p in payloads]
        taken = await self.items.existing_lemmas(lemmas)

        created: list[uuid.UUID] = []
        skipped: list[dict[str, str]] = []
        seen_in_batch: set[str] = set()

        for payload, lemma in zip(payloads, lemmas, strict=True):
            if lemma in taken:
                skipped.append({"term": payload.term, "reason": "A term with this lemma exists."})
                continue
            if lemma in seen_in_batch:
                # Two rows of the same import resolving to one lemma would hit
                # the unique index mid-flush and roll back the whole batch.
                skipped.append({"term": payload.term, "reason": "Duplicated within this request."})
                continue

            category = await self._require_category(payload.category_code)
            item = VocabularyItem(
                category_id=category.id,
                term=payload.term,
                lemma=lemma,
                is_phrase=payload.resolved_is_phrase(),
                weight=payload.weight,
                is_active=True,
                created_by=author.id,
            )
            await self.items.add(item)
            seen_in_batch.add(lemma)
            created.append(item.id)

        logger.info(
            "Bulk vocabulary import by %s: %d created, %d skipped",
            author.id,
            len(created),
            len(skipped),
        )
        return await self.items.list_by_ids(created), skipped

    async def get_item(self, item_id: uuid.UUID) -> VocabularyItem:
        item = await self.items.get_with_category(item_id)
        if item is None:
            raise VocabularyItemNotFoundError()
        return item

    async def update_item(
        self, item_id: uuid.UUID, payload: VocabularyItemUpdate
    ) -> VocabularyItem:
        item = await self.get_item(item_id)

        if payload.category_code is not None:
            category = await self._require_category(payload.category_code)
            # Assign the relationship, not just the foreign key: the reload
            # below returns this same instance from the session's identity map
            # rather than re-querying, so a stale `category` would make the
            # response report the old category name.
            item.category = category
            item.category_id = category.id

        if payload.term is not None:
            item.term = payload.term
            # Kept derived rather than client-supplied so it can never
            # disagree with the term, exactly as at creation.
            item.is_phrase = " " in payload.term

        if payload.lemma is not None:
            lemma = normalize_lemma(payload.lemma)
            clash = await self.items.get_by_lemma(lemma)
            if clash is not None and clash.id != item.id:
                raise DuplicateVocabularyTermError(
                    f"Lemma {lemma!r} is already used by {clash.term!r}."
                )
            item.lemma = lemma
        elif payload.term is not None and payload.lemma is None:
            # The term changed but no lemma was given. Leave the lemma alone:
            # re-deriving it would silently break detection for a term whose
            # lemma was deliberately hand-set ("higher than" -> "high than").
            pass

        if payload.weight is not None:
            item.weight = payload.weight
        if payload.is_active is not None:
            item.is_active = payload.is_active

        await self.items.db.flush()
        return await self._reload(item.id)

    async def deactivate_item(self, item_id: uuid.UUID) -> VocabularyItem:
        """Soft delete. The row stays so historical scores remain readable."""
        item = await self.get_item(item_id)
        item.is_active = False
        await self.items.db.flush()
        logger.info("Vocabulary term %r deactivated", item.term)
        return await self._reload(item.id)

    async def _reload(self, item_id: uuid.UUID) -> VocabularyItem:
        """Re-read with the category eagerly loaded, for serialisation."""
        item = await self.items.get_with_category(item_id)
        if item is None:  # pragma: no cover - the row was just written
            raise VocabularyItemNotFoundError()
        return item
