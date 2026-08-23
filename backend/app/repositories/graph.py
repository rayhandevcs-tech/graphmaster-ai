"""Graph and per-graph target vocabulary data access."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import selectinload

from app.models.content import Graph, GraphTargetVocabulary, VocabularyItem
from app.models.enums import Difficulty, GraphType
from app.models.submission import Submission
from app.repositories.base import BaseRepository


class GraphRepository(BaseRepository[Graph]):
    model = Graph

    async def get_with_targets(self, graph_id: uuid.UUID) -> Graph | None:
        stmt = (
            select(Graph)
            .where(Graph.id == graph_id)
            .options(
                selectinload(Graph.target_vocabulary)
                .selectinload(GraphTargetVocabulary.vocabulary_item)
                .selectinload(VocabularyItem.category)
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def build_list_query(
        self,
        *,
        graph_type: GraphType | None = None,
        difficulty: Difficulty | None = None,
        search: str | None = None,
        is_published: bool | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Select[Any]:
        stmt = select(Graph)
        if graph_type is not None:
            stmt = stmt.where(Graph.graph_type == graph_type.value)
        if difficulty is not None:
            stmt = stmt.where(Graph.difficulty == difficulty.value)
        if is_published is not None:
            stmt = stmt.where(Graph.is_published == is_published)
        if created_by is not None:
            stmt = stmt.where(Graph.created_by == created_by)
        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(or_(Graph.title.ilike(pattern), Graph.prompt.ilike(pattern)))
        return stmt.order_by(Graph.created_at.desc())

    async def random_published(
        self,
        *,
        graph_type: GraphType | None = None,
        difficulty: Difficulty | None = None,
        exclude_id: uuid.UUID | None = None,
    ) -> Graph | None:
        """One random published graph.

        Ordering by ``random()`` scans the table, which is the wrong shape for
        millions of rows but exactly right for a practice library of tens or
        hundreds — and unlike an offset-based pick it needs no second query to
        learn the row count.
        """
        stmt = select(Graph).where(Graph.is_published.is_(True))
        if graph_type is not None:
            stmt = stmt.where(Graph.graph_type == graph_type.value)
        if difficulty is not None:
            stmt = stmt.where(Graph.difficulty == difficulty.value)
        if exclude_id is not None:
            stmt = stmt.where(Graph.id != exclude_id)
        stmt = stmt.order_by(func.random()).limit(1)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def has_submissions(self, graph_id: uuid.UUID) -> bool:
        stmt = select(Submission.id).where(Submission.graph_id == graph_id).limit(1)
        return (await self.db.execute(stmt)).first() is not None

    # ── Target vocabulary ────────────────────────────────────────────────────

    async def list_targets(self, graph_id: uuid.UUID) -> list[GraphTargetVocabulary]:
        stmt = (
            select(GraphTargetVocabulary)
            .where(GraphTargetVocabulary.graph_id == graph_id)
            .options(
                selectinload(GraphTargetVocabulary.vocabulary_item).selectinload(
                    VocabularyItem.category
                )
            )
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def replace_targets(
        self, graph_id: uuid.UUID, entries: Sequence[tuple[uuid.UUID, bool]]
    ) -> None:
        """Set the target list to exactly ``entries``.

        Delete-then-insert rather than a diff: the set is small, and computing
        a minimal change would be more code for no observable difference.
        """
        await self.db.execute(
            delete(GraphTargetVocabulary).where(GraphTargetVocabulary.graph_id == graph_id)
        )
        for item_id, is_required in entries:
            self.db.add(
                GraphTargetVocabulary(
                    graph_id=graph_id,
                    vocabulary_item_id=item_id,
                    is_required=is_required,
                )
            )
        await self.db.flush()

    async def required_target_counts(self, graph_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Required-term counts keyed by graph, in one query.

        Listing graphs otherwise costs one count per row.
        """
        if not graph_ids:
            return {}
        stmt = (
            select(GraphTargetVocabulary.graph_id, func.count())
            .where(
                GraphTargetVocabulary.graph_id.in_(list(graph_ids)),
                GraphTargetVocabulary.is_required.is_(True),
            )
            .group_by(GraphTargetVocabulary.graph_id)
        )
        return {row[0]: int(row[1]) for row in (await self.db.execute(stmt)).all()}
