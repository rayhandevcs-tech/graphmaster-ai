"""Analysis endpoints (FR-6.x).

The engine's standalone surface. Sprint 6 wires the same service into
``POST /submissions/{id}/analyze``, where the result is persisted and drives
XP and achievements; here it can be run against arbitrary text so a teacher can
see what their target list actually rewards before setting it as an assignment.

``GET /rubric`` is open to every signed-in role: it publishes the weights and
the word-count band and nothing else, which is what lets a student's screen
state the marking criteria without hardcoding them (FR-6.12).

The other two are restricted to teachers and administrators, which is a
product decision rather than a technical one:

* **Preview** hands back a full score with no submission recorded. Open to
  students, it would let them iterate a draft against the marker until it
  scored 100 and only then submit — turning the vocabulary score from a
  measure of their range into a search problem, and detaching XP from the work
  that earned it.
* **Targets** hands back the exact list the percentage is computed against.
  Given to a student before they write, the task stops being description and
  becomes transcription of a word list. Students still see every term they
  missed *after* scoring, which is where the list teaches something.

Neither restriction is a security boundary; say the word if the classroom
model wants them opened up.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from app.api.deps import AnalysisSvc, CurrentUser, TeacherUser, require_teacher
from app.core.rate_limit import ANALYZE_LIMIT, enforce
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    EngineStatusResponse,
    StudentRubricOut,
    TargetSummaryResponse,
    to_analysis_response,
)

router = APIRouter(tags=["analysis"])


@router.get(
    "/engine",
    response_model=EngineStatusResponse,
    summary="The deployed scoring rubric and language-model state",
    description=(
        "Reports the weights, tier thresholds and word-count band this server actually "
        "scores with, plus whether the spaCy model is installed. Clients render the "
        "marking criteria from this rather than hardcoding a copy, so a retuned rubric "
        "does not leave the UI describing rules the server no longer applies."
    ),
)
async def engine_status(_: TeacherUser, analysis: AnalysisSvc) -> EngineStatusResponse:
    return EngineStatusResponse(**analysis.engine_status())


@router.get(
    "/rubric",
    response_model=StudentRubricOut,
    summary="The marking criteria, as a student may see them",
    description=(
        "The two weights the final score is composed from, and the word-count band the "
        "task expects. Open to every signed-in role, which the two endpoints below are "
        "not.\n\n"
        "It carries neither of the things those withhold. There is no target vocabulary "
        "here — this endpoint never sees a graph — and no tier threshold, because a "
        "student who knows where the crown begins is writing to a number rather than "
        "describing a chart. The engine version and the language-model state are absent "
        "too: they are deployment facts a learner can do nothing with.\n\n"
        "It exists so the interface can state the criteria (FR-6.12) instead of "
        "hardcoding `70/30` and going on saying it after the rubric is retuned."
    ),
)
async def student_rubric(_: CurrentUser, analysis: AnalysisSvc) -> StudentRubricOut:
    return StudentRubricOut.model_validate(analysis.student_rubric())


@router.get(
    "/graphs/{graph_id}/targets",
    response_model=TargetSummaryResponse,
    dependencies=[Depends(require_teacher)],
    summary="The target vocabulary a submission would be scored against",
    description=(
        "`source` is `curated` when a teacher set the list and `default` when it was "
        "derived from the chart type because none was set (FR-5.6). Only the required "
        "terms form the denominator of the vocabulary percentage."
    ),
)
async def graph_targets(
    graph_id: uuid.UUID, user: TeacherUser, analysis: AnalysisSvc
) -> TargetSummaryResponse:
    graph = await analysis.graph_service.get_for(graph_id, viewer=user)
    return TargetSummaryResponse(graph_id=graph.id, **await analysis.target_summary(graph))


@router.post(
    "/graphs/{graph_id}/preview",
    response_model=AnalysisResponse,
    dependencies=[Depends(require_teacher)],
    summary="Score text against a graph without recording anything",
    description=(
        "Runs the full pipeline — detection, writing quality, scoring, tier and feedback — "
        "and stores nothing. Returns 404 for an unknown graph, 409 when the graph has no "
        "target vocabulary and none could be derived, 422 for an empty or over-long "
        "answer, and 503 when the language model is not installed on this server."
    ),
)
async def preview(
    graph_id: uuid.UUID,
    payload: AnalysisRequest,
    request: Request,
    user: TeacherUser,
    analysis: AnalysisSvc,
) -> AnalysisResponse:
    # Metered on the same bucket as scoring a real submission: parsing is the
    # most expensive thing this endpoint does and the limit exists to cap CPU,
    # which does not care whether the result was persisted.
    enforce(request, ANALYZE_LIMIT)

    graph, result = await analysis.preview(graph_id, payload.text, viewer=user)
    return to_analysis_response(graph.id, result)
