"""The engine against the shipped content.

A graph's target list is only as good as the answer it is meant to reward. The
seeded reference descriptions *are* the model answers a teacher is shown, so if
one of them cannot reach the crown against its own target list, the target list
is badly curated and no student will reach it either. These tests are as much
about the seed content as about the engine, and they caught three graphs whose
target lists asked for phrases their own model answer never used.
"""

from __future__ import annotations

import pytest

from app.models.enums import GraphType, RewardTier, UserRole
from app.nlp.analyzer import analyse
from app.nlp.defaults import MAX_DEFAULT_TARGETS
from app.services.analysis import AnalysisService
from app.services.graph import GraphService

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("spacy_model")]


@pytest.fixture
def seed_terms(seeded_vocabulary):
    from app.nlp.terms import TargetTerm

    def build(lemmas: list[str]) -> list[TargetTerm]:
        terms = []
        for lemma in lemmas:
            item = seeded_vocabulary[lemma]
            terms.append(
                TargetTerm(
                    term=item.term,
                    lemma=item.lemma,
                    category_code=item.category.code,
                    category_name=item.category.name,
                    is_phrase=bool(item.is_phrase),
                    is_required=True,
                    weight=float(item.weight),
                )
            )
        return terms

    return build


def sample_graphs():
    from app.db.seed.data import SAMPLE_GRAPHS

    return [pytest.param(g, id=g["graph_type"]) for g in SAMPLE_GRAPHS]


@pytest.mark.parametrize("graph", sample_graphs())
async def test_every_model_answer_reaches_the_crown(graph, seed_terms):
    result = analyse(graph["reference_description"], seed_terms(graph["targets"]))
    assert result.detection.missing == []
    assert result.score.vocabulary_percentage == 100.0
    assert result.score.reward_tier is RewardTier.CROWN


@pytest.mark.parametrize("graph", sample_graphs())
async def test_every_model_answer_meets_its_own_word_minimum(graph, seed_terms, settings):
    # Each prompt asks for at least 150 words. A model answer shorter than the
    # instruction it accompanies undermines the instruction.
    result = analyse(graph["reference_description"], seed_terms(graph["targets"]))
    assert result.word_count >= settings.TARGET_WORD_COUNT_MIN
    assert result.writing.word_count_score == 100.0


@pytest.mark.parametrize("graph", sample_graphs())
async def test_every_model_answer_opens_with_an_overview(graph, seed_terms):
    result = analyse(graph["reference_description"], seed_terms(graph["targets"]))
    assert result.writing.has_overview
    assert result.writing.overview_score == 100.0


@pytest.mark.parametrize("graph", sample_graphs())
async def test_every_target_list_is_a_reachable_size(graph):
    # PROJECT_PLAN §3.2: a denominator far above a dozen puts the crown out of
    # reach in a 150-word answer, which would hide the product's centrepiece.
    assert 1 <= len(graph["targets"]) <= 12


@pytest.mark.parametrize("graph", sample_graphs())
async def test_every_seeded_target_exists_in_the_library(graph, seeded_vocabulary):
    assert set(graph["targets"]) <= set(seeded_vocabulary)


# ── Target resolution against the real library ───────────────────────────────


@pytest.fixture
def service(db):
    from app.repositories.graph import GraphRepository
    from app.repositories.vocabulary import VocabularyItemRepository

    graphs = GraphRepository(db)
    items = VocabularyItemRepository(db)
    return AnalysisService(graphs, items, GraphService(graphs, items))


@pytest.mark.parametrize("graph_type", list(GraphType))
async def test_a_default_target_set_is_derivable_for_every_chart_type(
    service, graph_factory, seeded_vocabulary, user_factory, graph_type: GraphType
):
    teacher = await user_factory(role=UserRole.TEACHER)
    graph = await graph_factory(
        created_by=teacher.id, graph_type=graph_type.value, is_published=False
    )

    terms = await service.targets_for_graph(graph)
    required = [t for t in terms if t.is_required]
    assert 1 <= len(required) <= MAX_DEFAULT_TARGETS
    assert len({t.lemma for t in required}) == len(required)


async def test_a_generated_target_set_is_scoreable(
    service, graph_factory, seeded_vocabulary, user_factory
):
    teacher = await user_factory(role=UserRole.TEACHER)
    graph = await graph_factory(created_by=teacher.id, graph_type="line", is_published=False)

    result = await service.analyse_for_graph(
        graph,
        "Overall, output increased sharply. It rose from 120 to 410 over the period, "
        "and fell only once, in 2023.",
    )
    assert result.score.total_target_count > 0
    assert result.score.vocabulary_percentage > 0


async def test_an_empty_library_is_reported_rather_than_dividing_by_zero(
    service, graph_factory, user_factory
):
    from app.core.exceptions import NoTargetVocabularyError

    teacher = await user_factory(role=UserRole.TEACHER)
    graph = await graph_factory(created_by=teacher.id, is_published=False)

    with pytest.raises(NoTargetVocabularyError):
        await service.targets_for_graph(graph)
