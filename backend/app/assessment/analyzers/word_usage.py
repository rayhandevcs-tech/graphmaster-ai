"""Word usage (Feature 5).

**Every issue this analyzer produces is a suggestion, and that is a design
decision rather than a limitation.** The specification asks that acceptable
stylistic variation is never penalised, and word choice is where a marker is
most likely to mistake a preference for a rule. "Sales went up a lot" is not
wrong; it is a register a student writing academic English is being taught to
move away from. Telling them that is useful. Marking it as an error is not.

Detecting genuinely *incorrect* word choice — the wrong preposition, a word
used with the wrong sense — needs a model this platform does not have, and
guessing at it would produce exactly the confident false positives that teach
a student to ignore the whole panel. So it is not attempted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from app.assessment.issues import AssessmentIssue
from app.assessment.protocol import AnalyzerOutput, AssessmentContext
from app.assessment.text import chart_words, real_words, scale, token_span
from app.core.config import Settings
from app.models.enums import IssueCategory, IssueSeverity

if TYPE_CHECKING:  # pragma: no cover
    from spacy.tokens import Token

#: Uses of one content word before repetition is worth mentioning.
#:
#: Four, and only in an answer long enough for four to be a pattern. In a
#: 60-word answer four uses of "increase" is the subject; in a 200-word one it
#: is a habit.
REPETITION_THRESHOLD = 4
REPETITION_MIN_WORDS = 80

#: Distinct content lemmas as a share of content words. Measured over the
#: whole answer rather than a moving window: unlike the rubric's MATTR, this is
#: not scored, so length-stability matters less than being explainable to a
#: student who asks what it means.
RICHNESS_FLOOR = 0.35
RICHNESS_TARGET = 0.65
RICHNESS_MIN_WORDS = 60

#: Conversational usages, with the academic alternative a marker would expect.
#:
#: Curated deliberately short. Every entry is something a graph-description
#: rubric actually asks students to change, and nothing here is wrong English —
#: which is why each becomes a suggestion and none becomes an error.
INFORMAL: dict[str, tuple[str, str]] = {
    "big": ("substantial", "“big” is conversational"),
    "small": ("slight", "“small” is conversational"),
    "huge": ("considerable", "“huge” overstates for academic writing"),
    "tiny": ("marginal", "“tiny” overstates for academic writing"),
    "lots": ("many", "“lots” is informal"),
    "loads": ("many", "“loads” is informal"),
    "thing": ("figure", "“thing” is vague — name what it refers to"),
    "stuff": ("data", "“stuff” is vague — name what it refers to"),
    "kinda": ("somewhat", "“kinda” is spoken English"),
    "gonna": ("going to", "“gonna” is spoken English"),
}

#: Intensifiers that add emphasis without adding information.
HEDGES = frozenset({"very", "really", "quite", "pretty", "sort", "basically", "actually"})

#: Parts of speech that carry meaning. The repetition measure ignores the rest,
#: because an answer's unavoidable "the" and "of" say nothing about range.
CONTENT_POS = frozenset({"NOUN", "PROPN", "VERB", "ADJ", "ADV"})


class WordUsageAnalyzer:
    """Richness, repetition and register — reported, never penalised."""

    name = "word_usage"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, ctx: AssessmentContext) -> AnalyzerOutput:
        words = real_words(ctx.doc)
        content = [t for t in words if t.pos_ in CONTENT_POS and not t.is_stop and t.is_alpha]

        if not content:
            return AnalyzerOutput(metrics={"content_words": 0.0})

        lemmas = [t.lemma_.lower() for t in content]
        counts = Counter(lemmas)
        distinct = len(counts)
        richness = distinct / len(lemmas)

        # The subject of the answer is exempt from the repetition check.
        # Using the vocabulary the exercise marks you on *is* the exercise, and
        # a chart of three renewable sources cannot be described without
        # naming them repeatedly. Telling a student to vary "solar" or
        # "fluctuate" would undo the lesson.
        exempt = {t.lemma.lower() for t in ctx.targets.terms} | chart_words(ctx.chart_data)

        overused = {
            lemma: uses
            for lemma, uses in counts.items()
            if uses >= REPETITION_THRESHOLD and lemma not in exempt
        }

        issues: list[AssessmentIssue] = []
        issues.extend(_repetition_issues(ctx, content, overused, len(words)))
        issues.extend(_register_issues(ctx, words))
        issues.extend(_richness_issue(ctx, richness, len(words)))

        hedges = sum(1 for t in words if t.lemma_.lower() in HEDGES)
        # Gated the same way the issue is: "the smallest contributor" is
        # correct academic writing, so it must not quietly cost a mark either.
        informal = sum(1 for t in words if t.lemma_.lower() in INFORMAL and _is_plain_form(t))
        # The share of the answer spent on words it repeats. This, not the
        # distinct-lemma ratio, is what separates a description of one thing
        # from a description that keeps saying the same thing: a long answer
        # can repeat one word eight times and still look varied by ratio.
        repetition_load = sum(overused.values()) / len(lemmas)

        return AnalyzerOutput(
            issues=tuple(issues),
            score=_score(richness, repetition_load, informal, hedges, len(words)),
            metrics={
                "content_words": float(len(content)),
                "distinct_content_lemmas": float(distinct),
                "lexical_richness": round(richness, 4),
                "repeated_lemmas": float(len(overused)),
                "repetition_load": round(repetition_load, 4),
                "informal_usages": float(informal),
                "hedges": float(hedges),
            },
        )


def _repetition_issues(
    ctx: AssessmentContext,
    content: list[Token],
    overused: dict[str, int],
    word_count: int,
) -> list[AssessmentIssue]:
    """One issue per over-used word, anchored where it becomes over-use.

    Anchored at the fourth occurrence rather than the first: the first three
    were fine, and highlighting them would tell the student the wrong thing
    about which words to change.
    """
    if word_count < REPETITION_MIN_WORDS:
        return []

    positions: dict[str, list[Token]] = defaultdict(list)
    for token in content:
        positions[token.lemma_.lower()].append(token)

    issues: list[AssessmentIssue] = []
    for lemma, uses in overused.items():
        anchor = positions[lemma][REPETITION_THRESHOLD - 1]
        start, end = token_span(ctx, anchor)
        issues.append(
            AssessmentIssue(
                category=IssueCategory.WORD_USAGE,
                subtype="repeated_word",
                severity=IssueSeverity.INFO,
                original_text=anchor.text,
                explanation=(
                    f"“{lemma}” appears {uses} times. A synonym here would widen the range "
                    f"the description shows."
                ),
                start=start,
                end=end,
                confidence=0.7,
                source="repetition",
            )
        )
    return issues


def _register_issues(ctx: AssessmentContext, words: list[Token]) -> list[AssessmentIssue]:
    """Conversational usages, each with the word a marker would expect."""
    issues: list[AssessmentIssue] = []
    for token in words:
        lemma = token.lemma_.lower()
        replacement = INFORMAL.get(lemma)
        if replacement is None or not _is_plain_form(token):
            continue
        alternative, reason = replacement
        start, end = token_span(ctx, token)
        issues.append(
            AssessmentIssue(
                category=IssueCategory.WORD_USAGE,
                subtype="informal_register",
                severity=IssueSeverity.INFO,
                original_text=token.text,
                suggested_text=alternative,
                explanation=(
                    f"{reason}. In academic description, “{alternative}” is the expected "
                    f"choice — this is a preference, not a mistake."
                ),
                start=start,
                end=end,
                confidence=0.75,
                source="register",
            )
        )
    return issues


def _is_plain_form(token: Token) -> bool:
    """Whether the word is in its base form rather than a comparison.

    "A big rise" is the register a graph-description rubric asks a student to
    change. "The smallest contributor" is not — a superlative is how a
    comparison between series is *correctly* expressed, and flagging it would
    penalise the very structure the exercise teaches. spaCy tags the two
    apart, so the distinction costs one lookup.
    """
    return token.tag_ not in {"JJR", "JJS", "RBR", "RBS"}


def _richness_issue(
    ctx: AssessmentContext, richness: float, word_count: int
) -> list[AssessmentIssue]:
    if word_count < RICHNESS_MIN_WORDS or richness >= RICHNESS_FLOOR:
        return []
    return [
        AssessmentIssue(
            category=IssueCategory.WORD_USAGE,
            subtype="narrow_vocabulary_range",
            severity=IssueSeverity.INFO,
            original_text="",
            explanation=(
                "The same words carry most of this description. Reaching for a second way "
                "to say “rose” or “fell” is what the vocabulary score is measuring."
            ),
            start=0,
            end=len(ctx.text),
            confidence=0.7,
            source="richness",
        )
    ]


#: Ceilings on what each penalty can take off. A student with a rich answer
#: and three casual words must not be marked down to a poor one.
MAX_REGISTER_PENALTY = 25.0
MAX_REPETITION_PENALTY = 30.0


def _score(
    richness: float, repetition_load: float, informal: int, hedges: int, word_count: int
) -> float:
    """Richness, less what repetition and the register cost.

    Diagnostic only — it appears beside the vocabulary score and never inside
    it. Both penalties are capped, and both are proportional: one casual word
    in two hundred is not the same finding as one in twenty.
    """
    base = scale(richness, RICHNESS_FLOOR, RICHNESS_TARGET)
    if word_count == 0:
        return base

    per_hundred = 100.0 * (informal + hedges) / word_count
    register = min(MAX_REGISTER_PENALTY, per_hundred * 5.0)
    repetition = min(MAX_REPETITION_PENALTY, repetition_load * 100.0 * 0.8)

    return round(max(0.0, base - register - repetition), 2)


__all__ = ["WordUsageAnalyzer"]
