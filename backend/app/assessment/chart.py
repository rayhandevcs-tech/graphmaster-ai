"""What the chart actually says.

The reason graph-accuracy analysis is possible at all is that a graph is stored
as structured data rather than as a picture (02-database-schema §3.2). This
module turns that data into a small set of facts a claim can be checked
against — and, just as importantly, records where the data is too ambiguous for
any claim about it to be judged.

Nothing here reads the student's writing.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from app.assessment.text import words_in
from app.models.enums import GraphType

#: Net change, as a share of the series' typical level, below which the series
#: is called stable rather than rising or falling.
#:
#: Measured against the mean, **not** against the series' own range. Against
#: the range, a genuinely flat line is the worst case: readings of
#: 230, 240, 235, 250 span only 20, so a net rise of 20 reads as 100% movement
#: and the analyzer contradicts a student who correctly wrote "remained
#: stable". The flatter the series, the more confidently it would have been
#: called a trend — the exact inverse of what is wanted.
#:
#: Against the mean, that series moves 8% and is stable, while 5 → 410 moves
#: 247% and is not.
STABLE_BAND = 0.15

#: Direction changes before a series is described as fluctuating.
#:
#: Two, not one: a single peak is a rise then a fall, which is a shape with its
#: own vocabulary. Genuine fluctuation is the pattern that keeps changing its
#: mind.
FLUCTUATION_TURNS = 2

#: Movement below this share of the range is noise, not a turning point. Without
#: it, floating-point wobble in a flat series reads as fluctuation.
TURN_THRESHOLD = 0.05

#: Chart types with an ordered axis, where "rose" and "fell" mean something.
#:
#: A pie chart is one snapshot of proportions, and a bar chart's categories may
#: be in any order — "sales rose" about a bar chart of five countries is not a
#: claim this module can judge, so it does not try.
SEQUENTIAL_TYPES = frozenset({GraphType.LINE, GraphType.AREA})

#: Words too generic to identify a series. "Total revenue" and "Total cost"
#: share "total", so it distinguishes nothing.
LABEL_NOISE = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "in",
        "per",
        "and",
        "total",
        "number",
        "amount",
        "value",
        "values",
        "figure",
        "figures",
        "rate",
        "data",
        "series",
    }
)


@dataclass(frozen=True, slots=True)
class SeriesFact:
    """One dataset, reduced to what a description could claim about it."""

    label: str
    #: Words that identify *this* series and no other in the same chart. Empty
    #: when two series share all their words, which is when no claim can be
    #: attributed to either.
    distinctive_words: frozenset[str]
    values: tuple[float, ...]
    point_labels: tuple[str, ...]

    first: float
    last: float
    minimum: float
    maximum: float
    mean: float
    peak_label: str
    trough_label: str
    turning_points: int

    @property
    def net_change(self) -> float:
        return self.last - self.first

    @property
    def level(self) -> float:
        """The series' typical magnitude, for judging what counts as movement."""
        return statistics.fmean(abs(v) for v in self.values)

    @property
    def movement(self) -> float:
        """Net change as a share of the typical level. 0 for a series at zero."""
        scale = self.level
        return abs(self.net_change) / scale if scale else 0.0

    @property
    def is_stable(self) -> bool:
        return self.movement < STABLE_BAND

    @property
    def rises(self) -> bool:
        return not self.is_stable and self.net_change > 0

    @property
    def falls(self) -> bool:
        return not self.is_stable and self.net_change < 0

    @property
    def fluctuates(self) -> bool:
        return self.turning_points >= FLUCTUATION_TURNS

    @property
    def direction(self) -> str:
        """A one-word summary, for an explanation a student will read."""
        if self.rises:
            return "increase"
        if self.falls:
            return "decrease"
        return "stability"


@dataclass(frozen=True, slots=True)
class ChartFacts:
    """Every fact this chart supports, and the limits on judging them."""

    graph_type: GraphType | None
    point_labels: tuple[str, ...]
    series: tuple[SeriesFact, ...]

    @property
    def is_sequential(self) -> bool:
        """Whether "rose" and "fell" mean anything about this chart's axis."""
        return self.graph_type in SEQUENTIAL_TYPES

    @property
    def single_series(self) -> SeriesFact | None:
        """The only series, when there is only one.

        A claim about a one-series chart needs no subject resolution: there is
        nothing else it could be about. That covers most beginner graphs, and
        it is the safest attribution available.
        """
        return self.series[0] if len(self.series) == 1 else None

    def dominant(self, first: SeriesFact, second: SeriesFact) -> SeriesFact | None:
        """Whichever of two series is above the other at *every* reading.

        Pairwise, not chart-wide. A student comparing hydroelectric with wind
        has said nothing about solar, and asking "is either above everything
        else" would answer a question they did not ask — on a three-series
        chart where one line overtakes another, that returns nothing and every
        comparison goes unchecked.

        Deliberately strict about the pair, though: where the two lines cross,
        the claim depends on a period the student may not have named, so this
        returns ``None`` rather than guessing.
        """
        if len(first.values) != len(second.values) or not first.values:
            # Different lengths cannot be compared point by point, and
            # comparing their means would answer a different question.
            return None

        pairs = list(zip(first.values, second.values, strict=True))
        if all(mine > theirs for mine, theirs in pairs):
            return first
        if all(mine < theirs for mine, theirs in pairs):
            return second
        return None


def derive(chart_data: Mapping[str, Any] | None, graph_type: GraphType | None) -> ChartFacts | None:
    """Reduce a Chart.js payload to facts. ``None`` when there is nothing to reduce."""
    if not chart_data:
        return None

    labels = tuple(str(label) for label in chart_data.get("labels") or ())
    raw_datasets = [d for d in chart_data.get("datasets") or () if isinstance(d, Mapping)]
    if not labels or not raw_datasets:
        return None

    label_words = [words_in(str(d.get("label", ""))) - LABEL_NOISE for d in raw_datasets]

    series: list[SeriesFact] = []
    for index, dataset in enumerate(raw_datasets):
        fact = _series_fact(dataset, labels, _distinctive(label_words, index))
        if fact is not None:
            series.append(fact)

    if not series:
        return None
    return ChartFacts(graph_type=graph_type, point_labels=labels, series=tuple(series))


def _distinctive(label_words: list[set[str]], index: int) -> frozenset[str]:
    """Words in this series' label that appear in no other series' label."""
    others: set[str] = set()
    for position, words in enumerate(label_words):
        if position != index:
            others |= words
    return frozenset(label_words[index] - others)


def _series_fact(
    dataset: Mapping[str, Any], labels: tuple[str, ...], distinctive: frozenset[str]
) -> SeriesFact | None:
    """One dataset's facts, or ``None`` if it carries too few readings.

    ``None`` entries are dropped rather than treated as zero: Chart.js renders
    a gap for a missing reading, and reading it as zero would invent a
    catastrophic fall the student is then contradicted for not describing.
    """
    raw = dataset.get("data")
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes):
        return None

    pairs = [
        (labels[i] if i < len(labels) else str(i), float(value))
        for i, value in enumerate(raw)
        if isinstance(value, int | float) and not isinstance(value, bool)
    ]
    if len(pairs) < 2:
        # One reading is a value, not a trend, and nothing here can be claimed
        # about its shape.
        return None

    point_labels = tuple(label for label, _ in pairs)
    values = tuple(value for _, value in pairs)

    highest = max(range(len(values)), key=lambda i: values[i])
    lowest = min(range(len(values)), key=lambda i: values[i])

    return SeriesFact(
        label=str(dataset.get("label", "")).strip() or "Series",
        distinctive_words=distinctive,
        values=values,
        point_labels=point_labels,
        first=values[0],
        last=values[-1],
        minimum=values[lowest],
        maximum=values[highest],
        mean=statistics.fmean(values),
        peak_label=point_labels[highest],
        trough_label=point_labels[lowest],
        turning_points=_turning_points(values),
    )


def _turning_points(values: tuple[float, ...]) -> int:
    """How many times the series changes direction.

    Movements smaller than a twentieth of the range are ignored, so a nearly
    flat line does not read as fluctuation because of rounding in the data a
    teacher typed in.
    """
    span = max(values) - min(values)
    if span == 0:
        return 0

    threshold = span * TURN_THRESHOLD
    direction = 0
    turns = 0

    for previous, current in pairwise(values):
        delta = current - previous
        if abs(delta) < threshold:
            continue
        step = 1 if delta > 0 else -1
        if direction and step != direction:
            turns += 1
        direction = step

    return turns


__all__ = ["ChartFacts", "SeriesFact", "derive"]
