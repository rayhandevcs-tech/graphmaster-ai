"""Text measures shared by the diagnostic analyzers.

Kept out of ``app.nlp`` on purpose: nothing here feeds a score, and putting a
readability formula next to the scoring rubric would invite exactly the
confusion this whole design exists to prevent.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from app.assessment.protocol import AssessmentContext

if TYPE_CHECKING:  # pragma: no cover
    from spacy.tokens import Doc, Span, Token

#: A blank line, however it is spelled. Students paste from word processors,
#: which use CRLF, and from phones, which sometimes use a lone CR.
PARAGRAPH_BREAK = re.compile(r"(?:\r\n|\r|\n)\s*(?:\r\n|\r|\n)")

#: Vowel groups, for the syllable heuristic.
_VOWEL_RUN = re.compile(r"[aeiouy]+")

#: Vowel pairs that make one sound. Everything else adjacent — the "ua" of
#: "gradually", the "eo" of "geology" — is two syllables, and counting every
#: run as one is the single largest error a naive counter makes.
_DIPHTHONGS = frozenset(
    {
        "ai",
        "au",
        "ay",
        "ea",
        "ee",
        "ei",
        "ey",
        "ie",
        "oa",
        "oe",
        "oi",
        "oo",
        "ou",
        "oy",
        "ue",
        "ui",
        "ya",
        "ye",
    }
)

#: Endings that are one syllable however their vowels are spelled. Without
#: this, "fluctuation" splits its "io" and comes out one too high.
_ONE_SYLLABLE_ENDINGS = ("tion", "sion", "cion", "cious", "tious", "geous", "gious")


def span_in_original(ctx: AssessmentContext, start: int, end: int) -> tuple[int, int]:
    """Map a span of the parsed text back to the answer the student submitted.

    Every issue offset goes through here. The parse runs over normalised text —
    typographic quotes folded, whitespace collapsed, zero-width characters
    removed — so a character index into it is not an index into what the
    student wrote, and a highlight built from one lands on the wrong words.
    """
    return ctx.normalised.to_original(start, end)


def token_span(ctx: AssessmentContext, token: Token) -> tuple[int, int]:
    return span_in_original(ctx, token.idx, token.idx + len(token.text))


def sentence_span(ctx: AssessmentContext, sentence: Span) -> tuple[int, int]:
    return span_in_original(ctx, sentence.start_char, sentence.end_char)


def real_words(doc: Doc) -> list[Token]:
    """Tokens that count as words: not punctuation, not whitespace."""
    return [t for t in doc if not t.is_punct and not t.is_space]


def real_sentences(doc: Doc) -> list[Span]:
    """Sentences with at least one word in them.

    spaCy will happily call a stray bullet or a trailing quote a sentence, and
    counting those would drag the mean sentence length down for a student who
    did nothing wrong.
    """
    return [s for s in doc.sents if any(not t.is_punct and not t.is_space for t in s)]


def paragraph_count(text: str) -> int:
    """Paragraphs in the student's own text, not the normalised copy.

    Normalisation collapses whitespace runs, which erases the blank lines that
    make a paragraph — so this is one of the few measures that must read the
    original.
    """
    blocks = [block for block in PARAGRAPH_BREAK.split(text) if block.strip()]
    return len(blocks)


def syllables(word: str) -> int:
    """An approximate syllable count for an English word.

    A heuristic, and it is used for one thing only: a readability index that is
    itself reported as an indication rather than a grade. The alternatives are a
    pronunciation dictionary — which misses every word a student invents, and
    every proper noun — or a further dependency for a number nobody is marked
    on.

    Three rules, in order: strip an ending that is one syllable however it is
    spelled, count vowel runs while splitting the pairs that are not
    diphthongs, then drop a silent trailing "e". It is wrong on loanwords and
    on some names, and being one syllable out moves the reading-ease index by
    around a point — well inside the tolerance of a figure reported as an
    indication.
    """
    word = word.lower().strip("'-")
    if not word:
        return 0

    # Peeled off first: these endings are one syllable whatever their vowels
    # look like, and leaving them in makes every "-tion" word one too high.
    trailing = 0
    for ending in _ONE_SYLLABLE_ENDINGS:
        if word.endswith(ending) and len(word) > len(ending):
            word = word[: -len(ending)]
            trailing = 1
            break

    count = 0
    for run in _VOWEL_RUN.findall(word):
        count += 1 if len(run) == 1 or run[:2] in _DIPHTHONGS else 2

    # A trailing silent 'e' — "make", "large" — is a vowel run that is not a
    # syllable. But "the" and "be" are, so a one-syllable word keeps its count.
    if word.endswith("e") and not word.endswith(("le", "ee", "ye")) and count > 1:
        count -= 1

    return max(1, count + trailing)


def flesch_reading_ease(word_count: int, sentence_count: int, syllable_count: int) -> float:
    """The Flesch reading-ease index, clamped to 0–100.

    Higher is easier. Academic graph description sits comfortably in the 40–60
    band; the index is reported so a student can see *that* their writing is
    dense, not so they can be marked down for it. Clamped because the raw
    formula runs past both ends on short or unusual text and a negative
    "readability" reads as a bug.
    """
    if word_count == 0 or sentence_count == 0:
        return 0.0

    words_per_sentence = word_count / sentence_count
    syllables_per_word = syllable_count / word_count
    score = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
    return round(max(0.0, min(100.0, score)), 2)


def words_in(phrase: str) -> set[str]:
    """Lower-cased alphabetic words within a phrase.

    Targets and chart labels are often multi-word — "higher than", "Total
    revenue (£m)" — and every consumer here works one token at a time.
    """
    return set("".join(c if c.isalpha() else " " for c in phrase).lower().split())


def chart_words(chart_data: Mapping[str, Any] | None) -> frozenset[str]:
    """Every word written on the chart: labels, series names, axes and units.

    Two analyzers need this and for the same reason. A student describing a
    chart of Bangladeshi districts will write the district names — they are not
    misspellings, and repeating them is not a narrow vocabulary. They are the
    subject.
    """
    if not chart_data:
        return frozenset()

    words: set[str] = set()
    for label in chart_data.get("labels") or ():
        words |= words_in(str(label))

    for dataset in chart_data.get("datasets") or ():
        if isinstance(dataset, Mapping):
            words |= words_in(str(dataset.get("label", "")))

    for key in ("x_axis_label", "y_axis_label", "unit"):
        value = chart_data.get(key)
        if value:
            words |= words_in(str(value))

    return frozenset(w for w in words if w)


def scale(value: float, floor: float, ceiling: float) -> float:
    """Map ``value`` onto 0–100 across ``[floor, ceiling]``, clamped at both ends.

    The same shape as the writing engine's own scaler, deliberately duplicated
    rather than imported: that one belongs to the scoring rubric, and a change
    made there for a scoring reason must not silently retune a diagnostic.
    """
    if ceiling <= floor:  # pragma: no cover - configuration guard
        return 100.0 if value >= ceiling else 0.0
    fraction = (value - floor) / (ceiling - floor)
    return round(max(0.0, min(1.0, fraction)) * 100.0, 2)


__all__ = [
    "chart_words",
    "flesch_reading_ease",
    "paragraph_count",
    "real_sentences",
    "real_words",
    "scale",
    "sentence_span",
    "span_in_original",
    "syllables",
    "token_span",
    "words_in",
]
