"""Graph (practice content) endpoints (FR-3.x).

The response model differs by role: students receive ``GraphDetail``, which
has no ``reference_description`` field at all, while teachers and
administrators receive ``GraphAuthoringDetail``. Returning the model answer to
a student before they submit would let them copy it
(docs/architecture/04-api-design.md §3.5).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, GraphRepo, GraphSvc, TeacherUser
from app.models.enums import Difficulty, GraphType
from app.schemas.common import Page
from app.schemas.graph import (
    GraphAuthoringDetail,
    GraphCreate,
    GraphDetail,
    GraphPublishRequest,
    GraphSummary,
    GraphUpdate,
    TargetVocabularyOut,
    TargetVocabularyReplace,
)

router = APIRouter(tags=["graphs"])

GraphResponse = GraphAuthoringDetail | GraphDetail


def _detail_model(payload: dict, *, viewer) -> GraphResponse:
    model = GraphAuthoringDetail if viewer.can_manage_content else GraphDetail
    return model.model_validate(payload)


@router.get("", response_model=Page[GraphSummary], summary="Browse practice graphs")
async def list_graphs(
    user: CurrentUser,
    repo: GraphRepo,
    graphs: GraphSvc,
    graph_type: GraphType | None = None,
    difficulty: Difficulty | None = None,
    search: str | None = Query(default=None, max_length=200),
    include_unpublished: bool = Query(
        default=False,
        description="Teachers and administrators only; ignored for students.",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[GraphSummary]:
    # Students are pinned to published content regardless of what they ask
    # for, so the flag cannot be used to browse drafts.
    published_filter = None if (user.can_manage_content and include_unpublished) else True

    stmt = repo.build_list_query(
        graph_type=graph_type,
        difficulty=difficulty,
        search=search,
        is_published=published_filter,
    )
    rows, total = await repo.paginate(stmt, page=page, page_size=page_size)
    return Page[GraphSummary].build(
        [GraphSummary.model_validate(s) for s in await graphs.summaries(list(rows))],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/random",
    response_model=GraphResponse,
    summary="A random published graph — the Start practice entry point",
)
async def get_random_graph(
    user: CurrentUser,
    graphs: GraphSvc,
    graph_type: GraphType | None = None,
    difficulty: Difficulty | None = None,
    exclude_id: uuid.UUID | None = Query(
        default=None, description="Skip this graph, so Try another never repeats itself"
    ),
) -> GraphResponse:
    graph = await graphs.get_random(
        graph_type=graph_type, difficulty=difficulty, exclude_id=exclude_id
    )
    return _detail_model(await graphs.detail_payload(graph, viewer=user), viewer=user)


@router.get("/{graph_id}", response_model=GraphResponse, summary="One graph")
async def get_graph(graph_id: uuid.UUID, user: CurrentUser, graphs: GraphSvc) -> GraphResponse:
    graph = await graphs.get_for(graph_id, viewer=user)
    return _detail_model(await graphs.detail_payload(graph, viewer=user), viewer=user)


# ── Authoring ────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=GraphAuthoringDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a graph (teachers and administrators)",
    description=(
        "The graph starts unpublished. Set its target vocabulary, then publish — "
        "a graph with no required target terms cannot be scored."
    ),
)
async def create_graph(
    payload: GraphCreate, teacher: TeacherUser, graphs: GraphSvc
) -> GraphAuthoringDetail:
    graph = await graphs.create(payload, author=teacher)
    return GraphAuthoringDetail.model_validate(await graphs.detail_payload(graph, viewer=teacher))


@router.patch(
    "/{graph_id}",
    response_model=GraphAuthoringDetail,
    summary="Update a graph (teachers and administrators)",
)
async def update_graph(
    graph_id: uuid.UUID, payload: GraphUpdate, teacher: TeacherUser, graphs: GraphSvc
) -> GraphAuthoringDetail:
    graph = await graphs.update(graph_id, payload, actor=teacher)
    return GraphAuthoringDetail.model_validate(await graphs.detail_payload(graph, viewer=teacher))


@router.post(
    "/{graph_id}/publish",
    response_model=GraphAuthoringDetail,
    summary="Publish or unpublish a graph (teachers and administrators)",
)
async def publish_graph(
    graph_id: uuid.UUID,
    payload: GraphPublishRequest,
    teacher: TeacherUser,
    graphs: GraphSvc,
) -> GraphAuthoringDetail:
    graph = await graphs.set_published(graph_id, published=payload.is_published, actor=teacher)
    return GraphAuthoringDetail.model_validate(await graphs.detail_payload(graph, viewer=teacher))


@router.delete(
    "/{graph_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an unattempted graph (author or administrator)",
    description=(
        "Returns 409 once any student has attempted the graph — unpublish it instead, "
        "so their scores keep their context."
    ),
)
async def delete_graph(graph_id: uuid.UUID, teacher: TeacherUser, graphs: GraphSvc) -> Response:
    await graphs.delete(graph_id, actor=teacher)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Target vocabulary ────────────────────────────────────────────────────────


@router.get(
    "/{graph_id}/target-vocabulary",
    response_model=list[TargetVocabularyOut],
    summary="The curated target set (teachers and administrators)",
)
async def list_target_vocabulary(
    graph_id: uuid.UUID, _: TeacherUser, graphs: GraphSvc
) -> list[TargetVocabularyOut]:
    return [TargetVocabularyOut.model_validate(t) for t in await graphs.list_targets(graph_id)]


@router.put(
    "/{graph_id}/target-vocabulary",
    response_model=list[TargetVocabularyOut],
    summary="Replace the target set (teachers and administrators)",
    description=(
        "Required terms form the denominator of the vocabulary percentage. Scoping the "
        "target set per graph rather than to the whole library is what keeps the crown "
        "tier reachable — see docs/PROJECT_PLAN.md §3.2."
    ),
)
async def replace_target_vocabulary(
    graph_id: uuid.UUID,
    payload: TargetVocabularyReplace,
    teacher: TeacherUser,
    graphs: GraphSvc,
) -> list[TargetVocabularyOut]:
    rows = await graphs.replace_targets(graph_id, payload.items, actor=teacher)
    return [TargetVocabularyOut.model_validate(t) for t in rows]
