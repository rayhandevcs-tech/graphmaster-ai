"""Vocabulary library data access."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import selectinload

from app.models.content import VocabularyCategory, VocabularyItem
from app.repositories.base import BaseRepository


class VocabularyCategoryRepository(BaseRepository[VocabularyCategory]):
    model = VocabularyCategory

    async def list_all(self) -> list[VocabularyCategory]:
        stmt = select(VocabularyCategory).order_by(
            VocabularyCategory.display_order, VocabularyCategory.name
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_code(self, code: str) -> VocabularyCategory | None:
        stmt = select(VocabularyCategory).where(VocabularyCategory.code == code.strip().lower())
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def active_item_counts(self) -> dict[uuid.UUID, int]:
        """Active term counts keyed by category.

        One grouped query rather than a count per category, so listing the
        seven categories stays a two-query operation however the library grows.
        """
        stmt = (
            select(VocabularyItem.category_id, func.count())
            .where(VocabularyItem.is_active.is_(True))
            .group_by(VocabularyItem.category_id)
        )
        return {row[0]: int(row[1]) for row in (await self.db.execute(stmt)).all()}


class VocabularyItemRepository(BaseRepository[VocabularyItem]):
    model = VocabularyItem

    async def get_with_category(self, item_id: uuid.UUID) -> VocabularyItem | None:
        stmt = (
            select(VocabularyItem)
            .where(VocabularyItem.id == item_id)
            .options(selectinload(VocabularyItem.category))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_lemma(self, lemma: str) -> VocabularyItem | None:
        stmt = (
            select(VocabularyItem)
            .where(VocabularyItem.lemma == lemma)
            .options(selectinload(VocabularyItem.category))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def existing_lemmas(self, lemmas: Sequence[str]) -> set[str]:
        """Which of ``lemmas`` are already taken.

        Used by the bulk importer to classify a whole batch in one round trip
        instead of one SELECT per candidate term.
        """
        if not lemmas:
            return set()
        stmt = select(VocabularyItem.lemma).where(VocabularyItem.lemma.in_(list(lemmas)))
        return {row[0] for row in (await self.db.execute(stmt)).all()}

    def build_list_query(
        self,
        *,
        category_code: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> Select[Any]:
        stmt = (
            select(VocabularyItem)
            .join(VocabularyItem.category)
            .options(selectinload(VocabularyItem.category))
        )
        if category_code:
            stmt = stmt.where(VocabularyCategory.code == category_code.strip().lower())
        if is_active is not None:
            stmt = stmt.where(VocabularyItem.is_active == is_active)
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(VocabularyItem.term.ilike(pattern), VocabularyItem.lemma.ilike(pattern))
            )
        return stmt.order_by(VocabularyCategory.display_order, VocabularyItem.term)

    async def list_by_ids(self, item_ids: Sequence[uuid.UUID]) -> list[VocabularyItem]:
        if not item_ids:
            return []
        stmt = (
            select(VocabularyItem)
            .where(VocabularyItem.id.in_(list(item_ids)))
            .options(selectinload(VocabularyItem.category))
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_active(self) -> list[VocabularyItem]:
        stmt = (
            select(VocabularyItem)
            .where(VocabularyItem.is_active.is_(True))
            .options(selectinload(VocabularyItem.category))
            .order_by(VocabularyItem.lemma)
        )
        return list((await self.db.execute(stmt)).scalars().all())
