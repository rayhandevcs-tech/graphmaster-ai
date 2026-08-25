"""Analysis service: turns database rows into an engine call and back.

The engine in ``app.nlp`` knows nothing about the database. This layer is the
bridge — it resolves which terms a graph asks for, hands them over, and returns
the result. Sprint 6's submission pipeline calls the same two methods rather
than reaching into the engine itself, so the target-resolution rules below
apply identically to a preview and to a scored submission.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import NoTargetVocabularyError
from app.models.content import Graph, GraphTargetVocabulary, VocabularyItem
from app.models.enums import Gender, GraphType
from app.models.identity import User
from app.nlp.analyzer import AnalysisResult, analyse
from app.nlp.defaults import MAX_DEFAULT_TARGETS, TERMS_PER_CATEGORY, default_categories
from app.nlp.pipeline import is_available, pipeline_info
from app.nlp.scoring import engine_version, rubric
from app.nlp.terms import TargetTerm
from app.repositories.graph import GraphRepository
from app.repositories.vocabulary import VocabularyItemRepository
from app.services.graph import GraphService


class AnalysisService:
    def __init__(
        self,
        graphs: GraphRepository,
        vocabulary: VocabularyItemRepository,
        graph_service: GraphService,
        settings: Settings | None = None,
    ) -> None:
        self.graphs = graphs
        self.vocabulary = vocabulary
        self.graph_service = graph_service
        self.settings = settings or get_settings()

    # ── Engine state ─────────────────────────────────────────────────────────

    def engine_status(self) -> dict[str, Any]:
        """What the server can do and by what rules, for the engine endpoint."""
        return {
            "available": is_available(),
            "engine_version": engine_version(self.settings),
            "pipeline": pipeline_info(),
            "rubric": rubric(self.settings),
        }

    # ── Target resolution ────────────────────────────────────────────────────

    async def targets_for_graph(self, graph: Graph) -> list[TargetTerm]:
        """The target set a submission against ``graph`` is scored on.

        A curated set always wins. The type-derived fallback exists for a draft
        a teacher is previewing before curating it (FR-5.6) — publishing is
        already blocked without required targets, so a *published* graph never
        reaches the fallback.
        """
        targets = await self.graphs.list_targets(graph.id)
        curated = [_from_target(t) for t in targets if t.vocabulary_item.is_active]

        if any(term.is_required for term in curated):
            return curated

        fallback = await self._default_targets(GraphType(graph.graph_type))
        if not fallback:
            raise NoTargetVocabularyError(
                "This graph has no target vocabulary, and no default set could be "
                "derived because the vocabulary library is empty."
            )
        # Any curated optional terms survive alongside the generated required
        # set: a teacher who added bonus vocabulary but no required terms meant
        # the bonus to count.
        return fallback + [term for term in curated if not term.is_required]

    async def _default_targets(self, graph_type: GraphType) -> list[TargetTerm]:
        """A default set drawn from the categories relevant to ``graph_type``.

        Terms are taken lightest-first within each category, so a generated set
        is the accessible vocabulary rather than the showiest — a student
        meeting an uncurated graph should not face a harder target list than one
        meeting a curated one.
        """
        items = await self.vocabulary.list_active()
        by_category: dict[str, list[VocabularyItem]] = {}
        for item in items:
            by_category.setdefault(item.category.code, []).append(item)

        for bucket in by_category.values():
            bucket.sort(key=lambda i: (float(i.weight), i.term))

        chosen: list[TargetTerm] = []
        for code in default_categories(graph_type):
            for item in by_category.get(code, [])[:TERMS_PER_CATEGORY]:
                if len(chosen) >= MAX_DEFAULT_TARGETS:
                    return chosen
                chosen.append(_from_item(item, is_required=True))
        return chosen

    # ── Analysis ─────────────────────────────────────────────────────────────

    async def analyse_for_graph(
        self,
        graph: Graph,
        text: str,
        *,
        student: User | None = None,
    ) -> AnalysisResult:
        """Analyse ``text`` as an answer to ``graph``."""
        targets = await self.targets_for_graph(graph)
        gender = Gender(student.gender) if student and student.gender else None
        return analyse(
            text,
            targets,
            settings=self.settings,
            graph_type=GraphType(graph.graph_type),
            gender=gender,
            # The chart itself, for the diagnostic analyzers. The spelling
            # checker exempts every word written on it, and sprint 17's graph
            # accuracy analyzer checks the student's claims against it. The
            # scoring engine ignores it entirely.
            chart_data=graph.chart_data,
        )

    async def preview(
        self, graph_id: uuid.UUID, text: str, *, viewer: User
    ) -> tuple[Graph, AnalysisResult]:
        """Score ``text`` against a graph without recording anything.

        Draft visibility is delegated to the graph service, so a preview cannot
        become a way to read an unpublished graph's targets.
        """
        graph = await self.graph_service.get_for(graph_id, viewer=viewer)
        return graph, await self.analyse_for_graph(graph, text, student=viewer)

    async def target_summary(self, graph: Graph) -> dict[str, Any]:
        """The resolved target set, and whether it was curated or generated."""
        curated = await self.graphs.list_targets(graph.id)
        is_curated = any(t.is_required and t.vocabulary_item.is_active for t in curated)
        terms = await self.targets_for_graph(graph)
        return {
            "source": "curated" if is_curated else "default",
            "required_count": sum(1 for t in terms if t.is_required),
            "optional_count": sum(1 for t in terms if not t.is_required),
            "terms": [
                {
                    "term": t.term,
                    "lemma": t.lemma,
                    "category": t.category_code,
                    "category_name": t.category_name,
                    "is_required": t.is_required,
                    "is_phrase": t.is_phrase,
                    "weight": t.weight,
                }
                for t in terms
            ],
        }


def _from_target(target: GraphTargetVocabulary) -> TargetTerm:
    return _from_item(target.vocabulary_item, is_required=target.is_required)


def _from_item(item: VocabularyItem, *, is_required: bool) -> TargetTerm:
    return TargetTerm(
        term=item.term,
        lemma=item.lemma,
        category_code=item.category.code,
        category_name=item.category.name,
        is_phrase=bool(item.is_phrase),
        is_required=is_required,
        weight=float(item.weight),
        item_id=item.id,
    )
