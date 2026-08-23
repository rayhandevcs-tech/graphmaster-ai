"""Writing-quality signals (FR-6.7).

Four equally weighted components, each normalised to 0–100. They are
**heuristics, not grammar checking**, and the API names them a writing
*signal* rather than a grade for that reason. The 30% weight reflects it: the
specification puts vocabulary at the centre and these measures are supporting
evidence (08-nlp-architecture.md §5.2).

Every band below is a judgement about academic graph description, not a
universal fact about English, so each carries the reasoning that picked it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from spacy.tokens import Doc

#: Window for the moving-average type-token ratio.
#:
#: Plain TTR falls monotonically as a text lengthens, so it would penalise a
#: longer answer for being longer — the opposite of the intended signal. A
#: moving average over a fixed window is length-stable. Fifty tokens is the
#: usual choice for short texts and fits inside a 150-word answer.
MATTR_WINDOW = 50

#: TTR values mapped to 0 and 100.
#:
#: Calibrated against worked answers rather than guessed, because the measure
#: here is not textbook MATTR: it runs over content lemmas with stop words
#: removed, which lifts the ratio well above the usual published figures.
#: Measured on this pipeline, a paragraph that repeats one verb throughout
#: scores 0.31, an ordinary student answer 0.57, and varied academic prose
#: 0.83. The anchors sit outside that range at both ends so a competent answer
#: is not pinned to 100 with no headroom left to reward genuine range.
MATTR_FLOOR = 0.45
MATTR_CEILING = 0.85

#: Content lemmas below which lexical diversity is treated as unproven.
#:
#: TTR is 1.0 for any text short enough that no word repeats, so a two-line
#: answer would otherwise earn full marks for range it never demonstrated —
#: rewarding the shortest answers most on the component meant to reward
#: vocabulary breadth. Below this count the score is attenuated in proportion
#: to how much text there was to measure.
DIVERSITY_CONFIDENCE_TOKENS = MATTR_WINDOW

#: Mean sentence length, in words, that earns full marks.
#:
#: Academic description needs complex sentences but not run-ons. Below the
#: band the writing is a list of fragments; above it, the reader loses the
#: thread.
SENTENCE_LENGTH_MIN = 12
SENTENCE_LENGTH_MAX = 25
SENTENCE_LENGTH_ZERO_LOW = 4
SENTENCE_LENGTH_ZERO_HIGH = 45

#: Proportion of sentences carrying a subordinate clause for full marks.
SUBORDINATION_TARGET = 0.35

#: Dependency labels that mark a clausal dependent in spaCy's English model.
SUBORDINATE_DEPS = frozenset({"advcl", "ccomp", "xcomp", "relcl", "acl", "csubj", "csubjpass"})

#: Word count above which the over-long taper bottoms out.
OVERLONG_ZERO_AT = 3.0

#: Floor for an over-long answer.
#:
#: Writing too much is a lesser failure than writing two lines: the student has
#: engaged with the task and produced material to work with. The taper
#: therefore stops well above zero, where the two-line answer's does not.
OVERLONG_FLOOR = 35.0

#: Discourse cues that introduce an overview statement.
#:
#: Matched on the normalised text, lower-cased. An overview is the single
#: most-taught convention of graph description writing, which is why it earns
#: a quarter of the writing score on its own.
OVERVIEW_CUES = (
    "overall",
    "in general",
    "generally",
    "in summary",
    "to summarise",
    "to summarize",
    "in conclusion",
    "to conclude",
    "the graph shows",
    "the graph illustrates",
    "the graph presents",
    "the chart shows",
    "the chart illustrates",
    "the chart presents",
    "the figure shows",
    "the figure illustrates",
    "it is clear that",
    "it can be seen that",
    "the most striking",
    "the most noticeable",
)

#: Sentences from the start within which an overview earns full marks.
OVERVIEW_LEAD_SENTENCES = 2

#: Partial credit for an overview that appears later than the opening.
#:
#: A summary in the final paragraph is a real overview and a real skill; it is
#: simply not where the convention puts it. Scoring it zero would teach the
#: student that summarising is wrong rather than that it belongs at the top.
OVERVIEW_LATE_SCORE = 60.0


@dataclass(frozen=True, slots=True)
class WritingQuality:
    word_count: int
    sentence_count: int
    word_count_score: float
    lexical_diversity_score: float
    sentence_structure_score: float
    overview_score: float
    mattr: float
    mean_sentence_length: float
    subordination_ratio: float
    has_overview: bool
    overview_sentence_index: int | None

    @property
    def score(self) -> float:
        """The writing-quality score: the four components, equally weighted."""
        return round(
            (
                self.word_count_score
                + self.lexical_diversity_score
                + self.sentence_structure_score
                + self.overview_score
            )
            / 4,
            2,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "components": {
                "word_count": round(self.word_count_score, 2),
                "lexical_diversity": round(self.lexical_diversity_score, 2),
                "sentence_structure": round(self.sentence_structure_score, 2),
                "overview": round(self.overview_score, 2),
            },
            "measures": {
                "mattr": round(self.mattr, 4),
                "mean_sentence_length": round(self.mean_sentence_length, 2),
                "subordination_ratio": round(self.subordination_ratio, 4),
                "has_overview": self.has_overview,
                "overview_sentence_index": self.overview_sentence_index,
            },
        }


def assess(doc: Doc, *, target_min: int, target_max: int) -> WritingQuality:
    """Score the four writing-quality components for ``doc``."""
    words = [t for t in doc if not t.is_punct and not t.is_space]
    sentences = [s for s in doc.sents if any(not t.is_punct and not t.is_space for t in s)]

    word_count = len(words)
    mattr, content_lemmas = _mattr(words)
    mean_length = _mean_sentence_length(sentences)
    subordination = _subordination_ratio(sentences)
    overview_index = _overview_sentence(sentences)

    return WritingQuality(
        word_count=word_count,
        sentence_count=len(sentences),
        word_count_score=word_count_adequacy(word_count, target_min, target_max),
        lexical_diversity_score=round(
            _scale(mattr, MATTR_FLOOR, MATTR_CEILING)
            * min(1.0, content_lemmas / DIVERSITY_CONFIDENCE_TOKENS),
            2,
        ),
        sentence_structure_score=round(
            (_sentence_length_score(mean_length) + _subordination_score(subordination)) / 2, 2
        ),
        overview_score=_overview_score(overview_index),
        mattr=mattr,
        mean_sentence_length=mean_length,
        subordination_ratio=subordination,
        has_overview=overview_index is not None,
        overview_sentence_index=overview_index,
    )


def word_count_adequacy(word_count: int, target_min: int, target_max: int) -> float:
    """Full marks inside the target band, tapering outside it.

    The two tapers are deliberately asymmetric — see :data:`OVERLONG_FLOOR`.
    """
    if target_min <= word_count <= target_max:
        return 100.0
    if word_count < target_min:
        if target_min <= 0:  # pragma: no cover - configuration guard
            return 100.0
        return round(max(0.0, 100.0 * word_count / target_min), 2)

    overshoot_limit = target_max * OVERLONG_ZERO_AT
    if word_count >= overshoot_limit:
        return OVERLONG_FLOOR
    fraction = (word_count - target_max) / (overshoot_limit - target_max)
    return round(100.0 - fraction * (100.0 - OVERLONG_FLOOR), 2)


def _mattr(words: list[Any]) -> tuple[float, int]:
    """Moving-average type-token ratio over content lemmas.

    Computed over lemmas rather than surface forms so that varying the
    inflection of one verb does not read as vocabulary range, and over content
    words only so that a text's unavoidable ``the`` and ``of`` do not dilute
    the measure for everyone equally.

    Returns the ratio and the number of lemmas it was measured over, because
    the ratio alone cannot distinguish real range from a text too short to
    repeat itself.
    """
    lemmas = [t.lemma_.lower() for t in words if not t.is_stop and (t.is_alpha or t.like_num)]
    if not lemmas:
        return (0.0, 0)
    if len(lemmas) <= MATTR_WINDOW:
        return (len(set(lemmas)) / len(lemmas), len(lemmas))

    ratios = [
        len(set(lemmas[i : i + MATTR_WINDOW])) / MATTR_WINDOW
        for i in range(len(lemmas) - MATTR_WINDOW + 1)
    ]
    return (sum(ratios) / len(ratios), len(lemmas))


def _mean_sentence_length(sentences: list[Any]) -> float:
    if not sentences:
        return 0.0
    lengths = [len([t for t in s if not t.is_punct and not t.is_space]) for s in sentences]
    return sum(lengths) / len(lengths)


def _subordination_ratio(sentences: list[Any]) -> float:
    if not sentences:
        return 0.0
    with_clause = sum(1 for s in sentences if any(t.dep_ in SUBORDINATE_DEPS for t in s))
    return with_clause / len(sentences)


def _sentence_length_score(mean_length: float) -> float:
    if mean_length <= 0:
        return 0.0
    if SENTENCE_LENGTH_MIN <= mean_length <= SENTENCE_LENGTH_MAX:
        return 100.0
    if mean_length < SENTENCE_LENGTH_MIN:
        return round(_scale(mean_length, SENTENCE_LENGTH_ZERO_LOW, SENTENCE_LENGTH_MIN), 2)
    return round(100.0 - _scale(mean_length, SENTENCE_LENGTH_MAX, SENTENCE_LENGTH_ZERO_HIGH), 2)


def _subordination_score(ratio: float) -> float:
    return round(_scale(ratio, 0.0, SUBORDINATION_TARGET), 2)


def _overview_sentence(sentences: list[Any]) -> int | None:
    """Index of the first sentence carrying an overview cue, if any."""
    for index, sentence in enumerate(sentences):
        lowered = sentence.text.lower()
        if any(cue in lowered for cue in OVERVIEW_CUES):
            return index
    return None


def _overview_score(index: int | None) -> float:
    if index is None:
        return 0.0
    return 100.0 if index < OVERVIEW_LEAD_SENTENCES else OVERVIEW_LATE_SCORE


def _scale(value: float, floor: float, ceiling: float) -> float:
    """Map ``value`` onto 0–100 across ``[floor, ceiling]``, clamped at both ends."""
    if ceiling <= floor:  # pragma: no cover - configuration guard
        return 100.0 if value >= ceiling else 0.0
    fraction = (value - floor) / (ceiling - floor)
    return round(max(0.0, min(1.0, fraction)) * 100.0, 2)
