"""Which pairs of submissions may be compared with each other.

The gates are this feature's main defence against its own false positives, and
they exclude a great deal of data on purpose. A baseline built from two of a
student's nine submissions is a weaker baseline than one built from nine — and
the way to say so is to build it from two and report that seven were excluded,
not to quietly build it from nine things that are not alike.

Every exclusion carries a stable reason slug, so a surface can say *why* a
comparison is missing rather than leaving a gap the reader fills in themselves.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.assessment.consistency.profile import ProfileRow


@dataclass(frozen=True, slots=True)
class Exclusion:
    """Why one prior submission cannot be compared with the current one."""

    #: Stable slug, and the grouping key for "what did the gates exclude".
    #: Phrased as a property of the pair, never of the student.
    reason: str
    #: Wording for a teacher. Rewritable without invalidating the slug.
    detail: str


#: Every reason a pair can be excluded, in the order they are checked.
REASONS: tuple[str, ...] = (
    "no_profile",
    "different_assessment_version",
    "different_input_method",
    "different_graph_type",
    "below_word_floor",
)


def comparable(
    current: ProfileRow,
    prior: ProfileRow,
    *,
    min_words: int,
) -> Exclusion | None:
    """``None`` when the two may be compared, otherwise why they may not.

    Order matters only for which reason is reported when several apply; the
    cheapest and most fundamental is checked first so the answer names the
    thing a teacher can most readily act on.
    """
    if not current.has_profile or not prior.has_profile:
        return Exclusion(
            "no_profile",
            "One of these submissions carries no writing profile.",
        )

    if current.assessment_version != prior.assessment_version:
        # The fingerprint records which analyzers ran and under what
        # configuration. Across a change to it the measures are not the same
        # quantities, so a line drawn through both is a line through two
        # different things. The series breaks here; it is never bridged.
        return Exclusion(
            "different_assessment_version",
            "These were assessed under different engine configurations, "
            "so their measurements are not comparable.",
        )

    if current.input_method != prior.input_method:
        # Handwriting reaches the engine through OCR. Missing full stops merge
        # sentences, recognition errors inflate spelling density, and both
        # move measures for reasons that have nothing to do with the writer.
        return Exclusion(
            "different_input_method",
            "One was handwritten and one was typed, which changes the "
            "measurements independently of the writing.",
        )

    if current.graph_type != prior.graph_type:
        # A pie chart asks for proportion language and a line chart for trend
        # language. Two answers to two chart types are not two samples of one
        # task.
        return Exclusion(
            "different_graph_type",
            "These describe different kinds of chart, which call for " "different language.",
        )

    if current.profile.word_count < min_words or prior.profile.word_count < min_words:
        return Exclusion(
            "below_word_floor",
            f"One is shorter than the {min_words}-word floor, below which "
            f"these measures are dominated by noise.",
        )

    return None


def partition(
    current: ProfileRow,
    priors: list[ProfileRow],
    *,
    min_words: int,
) -> tuple[list[ProfileRow], dict[str, int]]:
    """Split a student's earlier submissions into comparable and excluded.

    Returns the rows a baseline may be built from, and a count per reason for
    the rest. The counts are reported, never hidden: "built from 2 of 9" is
    the difference between a figure a teacher can weigh and one they cannot.
    """
    kept: list[ProfileRow] = []
    excluded: dict[str, int] = {}

    for prior in priors:
        exclusion = comparable(current, prior, min_words=min_words)
        if exclusion is None:
            kept.append(prior)
            continue
        excluded[exclusion.reason] = excluded.get(exclusion.reason, 0) + 1

    return kept, excluded


def segments(rows: list[ProfileRow]) -> list[tuple[str, list[ProfileRow]]]:
    """A chronological series split into runs of one assessment version.

    What a chart is drawn from. Each run is one unbroken line; the gaps
    between runs are gaps, not steps — the same rule that makes a trend line
    break where there is no data rather than interpolate across it.

    Rows are assumed already ordered oldest first, which is how the repository
    returns them.
    """
    out: list[tuple[str, list[ProfileRow]]] = []
    for row in rows:
        if out and out[-1][0] == row.assessment_version:
            out[-1][1].append(row)
            continue
        out.append((row.assessment_version, [row]))
    return out


__all__ = ["REASONS", "Exclusion", "comparable", "partition", "segments"]
