"""Graph (practice exercise) schemas.

The chart is stored as structured Chart.js data rather than as a rendered
image, so it is crisp at any size, themeable, and exposable as a data table for
screen readers (NFR-5.x). That makes the payload's shape part of the API
contract: these models validate it on the way in, because a malformed
``chart_data`` only surfaces as a blank canvas in the student's browser.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Difficulty, GraphType
from app.schemas.common import ORMModel
from app.schemas.vocabulary import VocabularyItemOut

MAX_LABELS = 60
MAX_DATASETS = 8


class ChartDataset(BaseModel):
    """One series.

    Extra keys are allowed and stored verbatim: Chart.js accepts dozens of
    styling options (``backgroundColor``, ``borderDash``, ``tension``…) and
    enumerating them here would mean editing this model every time a teacher
    wants a differently styled chart. JSON cannot carry functions, so nothing
    executable can arrive this way.
    """

    model_config = ConfigDict(extra="allow")

    label: Annotated[str, Field(min_length=1, max_length=120)]
    # None is meaningful: Chart.js renders it as a gap, which is how a series
    # with missing readings is drawn honestly rather than by interpolating.
    data: Annotated[list[float | None], Field(min_length=1)]


class ChartData(BaseModel):
    """A Chart.js-compatible ``data`` object plus the axis metadata a
    description needs.

    Axis labels are not decoration. "Sales in thousands of units" is the
    vocabulary a student is expected to reuse; without it the same chart could
    be describing anything.
    """

    model_config = ConfigDict(extra="allow")

    labels: Annotated[list[str], Field(min_length=2, max_length=MAX_LABELS)]
    datasets: Annotated[list[ChartDataset], Field(min_length=1, max_length=MAX_DATASETS)]
    x_axis_label: str | None = Field(default=None, max_length=120)
    y_axis_label: str | None = Field(default=None, max_length=120)
    unit: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _datasets_match_labels(self) -> ChartData:
        expected = len(self.labels)
        for index, dataset in enumerate(self.datasets):
            if len(dataset.data) != expected:
                # Chart.js does not complain about this; it silently plots the
                # shorter of the two, so a typo would quietly change what the
                # student is asked to describe.
                raise ValueError(
                    f"Dataset {index} ({dataset.label!r}) has {len(dataset.data)} points "
                    f"but there are {expected} labels. They must match."
                )
        return self


def validate_chart_for_type(chart: ChartData, graph_type: GraphType) -> None:
    """Apply the rules that depend on the chart type.

    Raises ``ValueError``; callers surface it through Pydantic so the client
    sees an ordinary 422 with a field path.
    """
    if graph_type is GraphType.PIE and len(chart.datasets) != 1:
        # A pie chart shows one series as proportions of a whole. Chart.js
        # will render a second dataset as a concentric ring, which is a
        # different exercise than the one the teacher chose.
        raise ValueError(
            f"A pie chart takes exactly one dataset, got {len(chart.datasets)}. "
            "Use a bar chart to compare several series."
        )

    if graph_type is GraphType.PIE:
        values = [v for v in chart.datasets[0].data if v is not None]
        if any(v < 0 for v in values):
            raise ValueError("A pie chart cannot show negative values.")
        if not values:
            raise ValueError("A pie chart needs at least one non-null value.")


# ── Target vocabulary ────────────────────────────────────────────────────────


class TargetVocabularyEntry(BaseModel):
    vocabulary_item_id: uuid.UUID
    is_required: bool = Field(
        default=True,
        description=(
            "Required terms form the denominator of the vocabulary percentage. "
            "Optional terms are credited when used but do not make the crown "
            "tier harder to reach."
        ),
    )


class TargetVocabularyReplace(BaseModel):
    """The full target set. This replaces whatever was there before."""

    items: Annotated[list[TargetVocabularyEntry], Field(max_length=60)]

    @model_validator(mode="after")
    def _reject_duplicates(self) -> TargetVocabularyReplace:
        seen = {entry.vocabulary_item_id for entry in self.items}
        if len(seen) != len(self.items):
            raise ValueError("The same vocabulary item is listed more than once.")
        return self


class TargetVocabularyOut(BaseModel):
    is_required: bool
    item: VocabularyItemOut


# ── Graph payloads ───────────────────────────────────────────────────────────


class GraphPreview(BaseModel):
    """Enough of the figures to draw a thumbnail, and deliberately no more.

    A practice card that shows only a type icon asks a student to choose
    between four graphs by reading four titles. Showing the shape of each one
    is the difference between a list and a library.

    This is not ``ChartData``. Sending the whole thing on every row would put
    axis labels, units and every Chart.js styling key a teacher has set into a
    twenty-row listing, and the card would then need a Chart.js instance per
    graph to draw something 200px wide with no legible axes anyway. What a
    thumbnail needs is the *shape*: the numbers, per series, in order. The
    client draws them as a few SVG paths.

    Nulls survive the trip because a gap in a series is part of its shape — a
    line that closes over a missing reading is a different graph.
    """

    series: Annotated[list[list[float | None]], Field(max_length=MAX_DATASETS)]


def chart_preview(chart_data: Any) -> dict[str, Any] | None:
    """The thumbnail payload for a stored ``chart_data`` blob.

    Reads defensively and returns ``None`` rather than raising. Every row that
    reaches this was validated by ``ChartData`` on the way in, but a listing is
    the wrong place to discover that one of twenty rows predates a validator or
    was written by a migration — a graph with an unreadable blob should appear
    in the library without a picture, not take the page down with it.
    """
    if not isinstance(chart_data, dict):
        return None

    datasets = chart_data.get("datasets")
    if not isinstance(datasets, list):
        return None

    series: list[list[float | None]] = []
    for dataset in datasets[:MAX_DATASETS]:
        if not isinstance(dataset, dict):
            continue
        points = dataset.get("data")
        if not isinstance(points, list):
            continue
        series.append([float(p) if isinstance(p, (int, float)) else None for p in points])

    return {"series": series} if series else None


class GraphSummary(ORMModel):
    id: uuid.UUID
    title: str
    graph_type: GraphType
    difficulty: Difficulty
    is_published: bool
    image_url: str | None
    target_vocabulary_count: int = Field(
        default=0, description="Required target terms — the scoring denominator"
    )
    prompt: str = Field(
        description="What the student is asked to do. On the summary because the "
        "practice card shows it under the thumbnail: the task is what a student "
        "chooses between, more than the title is."
    )
    preview: GraphPreview | None = Field(
        default=None,
        description="The series values, for a thumbnail. Null for a graph whose "
        "stored figures cannot be read as series — never a reason to drop the row.",
    )
    created_at: datetime


class GraphDetail(GraphSummary):
    """What a student receives.

    ``reference_description`` is deliberately absent from this model rather
    than merely omitted by the handler: it is a model answer, and a student who
    could fetch it before submitting would be scored on their copying. Keeping
    it out of the type makes the leak impossible rather than merely unlikely.
    See docs/architecture/04-api-design.md §3.5.
    """

    # Typed rather than ``dict[str, Any]``: the client renders Chart.js
    # straight from this, and an untyped blob there forces a cast in the one
    # place the shape actually matters. Every stored value was validated by
    # this same model on the way in, and ``extra="allow"`` keeps the styling
    # keys a teacher added.
    chart_data: ChartData


class GraphAuthoringDetail(GraphDetail):
    """What a teacher or administrator receives: everything, plus the targets."""

    reference_description: str | None
    created_by: uuid.UUID
    updated_at: datetime
    target_vocabulary: list[TargetVocabularyOut] = Field(default_factory=list)


class GraphCreate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=300)]
    prompt: Annotated[str, Field(min_length=10, max_length=4000)]
    graph_type: GraphType
    difficulty: Difficulty = Difficulty.BEGINNER
    chart_data: ChartData
    reference_description: str | None = Field(default=None, max_length=8000)
    image_url: str | None = Field(default=None, max_length=1000)
    target_vocabulary: list[TargetVocabularyEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_chart_for_type(self) -> GraphCreate:
        validate_chart_for_type(self.chart_data, self.graph_type)
        return self


class GraphUpdate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=300)] | None = None
    prompt: Annotated[str, Field(min_length=10, max_length=4000)] | None = None
    graph_type: GraphType | None = None
    difficulty: Difficulty | None = None
    chart_data: ChartData | None = None
    reference_description: str | None = Field(default=None, max_length=8000)
    image_url: str | None = Field(default=None, max_length=1000)


class GraphPublishRequest(BaseModel):
    is_published: bool = True
