"""Graph (practice content) business logic (FR-3.x, FR-6.5).

Two rules here are worth stating plainly:

* Students only ever see published graphs, and never the reference
  description before submitting (docs/architecture/04-api-design.md §3.5).
* A graph cannot be published without at least one *required* target term.
  The vocabulary percentage is ``detected / required targets``; publishing an
  empty target set would put a zero in that denominator and make the graph
  unscoreable — see docs/PROJECT_PLAN.md §3.2.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.exceptions import (
    GraphHasSubmissionsError,
    GraphNotFoundError,
    NoTargetVocabularyError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models.content import Graph, GraphTargetVocabulary
from app.models.enums import Difficulty, GraphType
from app.models.identity import User
from app.repositories.graph import GraphRepository
from app.repositories.vocabulary import VocabularyItemRepository
from app.schemas.graph import (
    ChartData,
    GraphCreate,
    GraphUpdate,
    TargetVocabularyEntry,
    chart_preview,
    validate_chart_for_type,
)
from app.services.vocabulary import serialize_item

logger = get_logger(__name__)


class GraphService:
    def __init__(self, graphs: GraphRepository, vocabulary: VocabularyItemRepository) -> None:
        self.graphs = graphs
        self.vocabulary = vocabulary

    # ── Reads ────────────────────────────────────────────────────────────────

    async def get_for(self, graph_id: uuid.UUID, *, viewer: User) -> Graph:
        graph = await self.graphs.get_with_targets(graph_id)
        if graph is None:
            raise GraphNotFoundError()
        if not graph.is_published and not viewer.can_manage_content:
            # Unpublished content reads as absent to students rather than as
            # forbidden, so the endpoint cannot be used to enumerate drafts.
            raise GraphNotFoundError()
        return graph

    async def get_random(
        self,
        *,
        graph_type: GraphType | None = None,
        difficulty: Difficulty | None = None,
        exclude_id: uuid.UUID | None = None,
    ) -> Graph:
        graph = await self.graphs.random_published(
            graph_type=graph_type, difficulty=difficulty, exclude_id=exclude_id
        )
        if graph is None:
            raise GraphNotFoundError(
                "No published graph matches those filters yet. Try removing a filter."
            )
        return graph

    async def summaries(self, graphs: list[Graph]) -> list[dict[str, Any]]:
        """Attach the required-target count to each row in one extra query."""
        counts = await self.graphs.required_target_counts([g.id for g in graphs])
        return [
            {
                "id": g.id,
                "title": g.title,
                "graph_type": g.graph_type,
                "difficulty": g.difficulty,
                "is_published": g.is_published,
                "image_url": g.image_url,
                "target_vocabulary_count": counts.get(g.id, 0),
                "prompt": g.prompt,
                "preview": chart_preview(g.chart_data),
                "created_at": g.created_at,
            }
            for g in graphs
        ]

    async def detail_payload(self, graph: Graph, *, viewer: User) -> dict[str, Any]:
        counts = await self.graphs.required_target_counts([graph.id])
        payload: dict[str, Any] = {
            "id": graph.id,
            "title": graph.title,
            "graph_type": graph.graph_type,
            "difficulty": graph.difficulty,
            "is_published": graph.is_published,
            "image_url": graph.image_url,
            "target_vocabulary_count": counts.get(graph.id, 0),
            "created_at": graph.created_at,
            "prompt": graph.prompt,
            "chart_data": graph.chart_data,
        }
        if viewer.can_manage_content:
            payload |= {
                "reference_description": graph.reference_description,
                "created_by": graph.created_by,
                "updated_at": graph.updated_at,
                "target_vocabulary": self.serialize_targets(graph.target_vocabulary),
            }
        return payload

    @staticmethod
    def serialize_targets(targets: list[GraphTargetVocabulary]) -> list[dict[str, Any]]:
        return [
            {"is_required": t.is_required, "item": serialize_item(t.vocabulary_item)}
            for t in sorted(
                targets,
                key=lambda t: (
                    t.vocabulary_item.category.display_order,
                    t.vocabulary_item.term,
                ),
            )
        ]

    # ── Writes ───────────────────────────────────────────────────────────────

    async def create(self, payload: GraphCreate, *, author: User) -> Graph:
        graph = Graph(
            title=payload.title,
            prompt=payload.prompt,
            graph_type=payload.graph_type.value,
            difficulty=payload.difficulty.value,
            chart_data=payload.chart_data.model_dump(mode="json", exclude_none=True),
            reference_description=payload.reference_description,
            image_url=payload.image_url,
            # Never published on creation: a graph with no target vocabulary
            # cannot be scored, and the targets are set in a separate step.
            is_published=False,
            created_by=author.id,
        )
        await self.graphs.add(graph)

        if payload.target_vocabulary:
            await self._write_targets(graph.id, payload.target_vocabulary)

        logger.info("Graph %r created by %s", graph.title, author.id)
        return await self._reload(graph.id)

    async def update(self, graph_id: uuid.UUID, payload: GraphUpdate, *, actor: User) -> Graph:
        graph = await self._require_graph(graph_id)

        # The chart shape rules depend on the type, and either half can change
        # in the same request — so validate the pair that will actually be
        # stored, not just the field that arrived.
        new_type = payload.graph_type or None
        if payload.chart_data is not None:
            effective_type = new_type or GraphType(graph.graph_type)
            validate_chart_for_type(payload.chart_data, effective_type)
            graph.chart_data = payload.chart_data.model_dump(mode="json", exclude_none=True)
        elif new_type is not None:
            # The type changed but the data did not; re-check the stored data
            # against the new type rather than letting a pie chart inherit
            # three datasets from its life as a bar chart.
            try:
                validate_chart_for_type(ChartData.model_validate(graph.chart_data), new_type)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        fields = payload.model_dump(exclude_unset=True, exclude={"chart_data", "graph_type"})
        for field, value in fields.items():
            setattr(graph, field, value)
        if new_type is not None:
            graph.graph_type = new_type.value
        if payload.difficulty is not None:
            graph.difficulty = payload.difficulty.value

        await self.graphs.db.flush()
        logger.info("Graph %s updated by %s", graph.id, actor.id)
        return await self._reload(graph.id)

    async def set_published(self, graph_id: uuid.UUID, *, published: bool, actor: User) -> Graph:
        graph = await self._require_graph(graph_id)

        if published:
            required = (await self.graphs.required_target_counts([graph.id])).get(graph.id, 0)
            if required == 0:
                raise NoTargetVocabularyError(
                    "This graph has no required target vocabulary, so a submission "
                    "could not be scored. Set its target terms before publishing."
                )

        graph.is_published = published
        await self.graphs.db.flush()
        logger.info(
            "Graph %s %s by %s", graph.id, "published" if published else "unpublished", actor.id
        )
        return await self._reload(graph.id)

    async def delete(self, graph_id: uuid.UUID, *, actor: User) -> None:
        graph = await self._require_graph(graph_id)

        if await self.graphs.has_submissions(graph_id):
            raise GraphHasSubmissionsError(
                "Students have already attempted this graph. Unpublish it instead — "
                "deleting it would orphan their scores."
            )

        if graph.created_by != actor.id and not actor.is_admin:
            # Editing is open to any teacher (the practice library is shared),
            # but deletion is irreversible, so it stays with the author or an
            # administrator.
            raise PermissionDeniedError(
                "Only the teacher who created this graph, or an administrator, can delete it."
            )

        await self.graphs.delete(graph)
        logger.info("Graph %s deleted by %s", graph_id, actor.id)

    # ── Target vocabulary ────────────────────────────────────────────────────

    async def list_targets(self, graph_id: uuid.UUID) -> list[dict[str, Any]]:
        await self._require_graph(graph_id)
        return self.serialize_targets(await self.graphs.list_targets(graph_id))

    async def replace_targets(
        self, graph_id: uuid.UUID, entries: list[TargetVocabularyEntry], *, actor: User
    ) -> list[dict[str, Any]]:
        graph = await self._require_graph(graph_id)

        if graph.is_published and not any(e.is_required for e in entries):
            # A published graph must stay scoreable, so emptying its required
            # set is refused rather than silently breaking every new attempt.
            raise NoTargetVocabularyError(
                "This graph is published, so it needs at least one required target term. "
                "Unpublish it first if you want to clear the target set."
            )

        await self._write_targets(graph_id, entries)

        logger.info("Targets for graph %s replaced by %s (%d)", graph_id, actor.id, len(entries))
        return self.serialize_targets(await self.graphs.list_targets(graph_id))

    async def _write_targets(
        self, graph_id: uuid.UUID, entries: list[TargetVocabularyEntry]
    ) -> None:
        item_ids = [e.vocabulary_item_id for e in entries]
        found = {i.id: i for i in await self.vocabulary.list_by_ids(item_ids)}

        missing = [str(i) for i in item_ids if i not in found]
        if missing:
            raise ValidationError(
                f"{len(missing)} vocabulary item(s) do not exist: {', '.join(missing[:5])}"
            )

        inactive = [found[i].term for i in item_ids if not found[i].is_active]
        if inactive:
            # A deactivated term is never detected, so targeting one would put
            # a permanently unreachable term in the scoring denominator.
            raise ValidationError(
                f"These terms are deactivated and cannot be targeted: {', '.join(inactive)}."
            )

        await self.graphs.replace_targets(
            graph_id, [(e.vocabulary_item_id, e.is_required) for e in entries]
        )

    # ── Internals ────────────────────────────────────────────────────────────

    async def _require_graph(self, graph_id: uuid.UUID) -> Graph:
        graph = await self.graphs.get_with_targets(graph_id)
        if graph is None:
            raise GraphNotFoundError()
        return graph

    async def _reload(self, graph_id: uuid.UUID) -> Graph:
        graph = await self.graphs.get_with_targets(graph_id)
        if graph is None:  # pragma: no cover - the row was just written
            raise GraphNotFoundError()
        return graph
