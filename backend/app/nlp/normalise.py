"""Text normalisation for analysis (FR-6.1).

Two things make this less trivial than "lowercase and strip punctuation":

**The original text is never mutated.** Detected terms are reported with
character offsets so the UI can highlight them where the student actually
wrote them. Normalisation therefore builds a parallel string *and* an index
map back into the original, rather than editing in place.

**Lowercasing and punctuation stripping are done by the matcher, not here.**
FR-6.1 asks for case- and punctuation-insensitive matching, and that is what
the engine delivers — but it delivers it by matching on spaCy's ``LOWER`` and
``LEMMA`` token attributes rather than by destroying the text first. Doing it
literally would be actively harmful: the part-of-speech tagger is trained on
cased text and degrades sharply on a lowercased input, and the POS tag is what
stops an unrelated homograph in a function-word role being counted as a
vocabulary hit (08-nlp-architecture.md §4.1). Punctuation never participates in
matching because matching is token-based, so removing it buys nothing and
would break the sentence segmentation the writing score depends on.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

#: Characters replaced before Unicode normalisation gets a say.
#:
#: NFKC leaves dashes and primes alone, but a student pasting from a word
#: processor gets typographic ones, and an OCR engine emits them from scanned
#: print. Left as-is they fragment tokens: an en dash between two words is not
#: a token separator to spaCy the way a hyphen-minus is.
CHARACTER_SUBSTITUTIONS = {
    "‘": "'",  # left single quote
    "’": "'",  # right single quote / typographic apostrophe
    "‚": "'",
    "‛": "'",
    "′": "'",  # prime
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "„": '"',
    "″": '"',  # double prime
    "‐": "-",  # hyphen
    "‑": "-",  # non-breaking hyphen
    "‒": "-",  # figure dash
    "–": "-",  # en dash
    "—": "-",  # em dash
    "―": "-",  # horizontal bar
    "−": "-",  # minus sign
}

#: Characters removed outright.
#:
#: Zero-width and bidirectional-control characters are invisible, so a student
#: cannot see them and would never suspect them, yet a zero-width space inside
#: a word silently prevents that word ever matching a vocabulary term. They
#: arrive routinely in text pasted from the web.
INVISIBLE_CHARACTERS = frozenset("​‌‍‎‏⁠﻿­‪‫‬‭‮")


@dataclass(frozen=True, slots=True)
class NormalisedText:
    """Normalised text alongside the original it came from."""

    text: str
    original: str
    #: ``offsets[i]`` is the index in ``original`` that ``text[i]`` came from.
    #: One entry longer than ``text`` so an exclusive end index always resolves.
    offsets: tuple[int, ...]

    def to_original(self, start: int, end: int) -> tuple[int, int]:
        """Translate a half-open span of ``text`` to a half-open span of ``original``.

        The end index is derived from the *last character in the span* rather
        than read straight out of the map. ``offsets[end]`` is where the
        character *after* the span came from, and because whitespace runs
        collapse that is not the same place the span ends — using it directly
        drags the highlight over the following space.

        Clamped rather than asserted: a caller handing over a span from a
        different string should get a harmless highlight, not a 500 in the
        middle of returning a student their score.
        """
        limit = len(self.text)
        if limit == 0:
            return (0, 0)
        start = max(0, min(start, limit))
        end = max(start, min(end, limit))
        if end == start:
            position = self.offsets[start]
            return (position, position)
        return (self.offsets[start], self.offsets[end - 1] + 1)

    def original_slice(self, start: int, end: int) -> str:
        """The student's own words for a span of the normalised text."""
        o_start, o_end = self.to_original(start, end)
        return self.original[o_start:o_end]


def normalise(text: str) -> NormalisedText:
    """Normalise ``text`` for analysis, keeping a map back to the original.

    Unicode normalisation is applied per character rather than to the whole
    string. Whole-string NFKC can compose or decompose across character
    boundaries, which makes the index map ambiguous; per-character NFKC covers
    every case that matters for English prose — ligatures, full-width forms,
    non-breaking spaces — and keeps each output character attributable to
    exactly one input character.
    """
    out: list[str] = []
    offsets: list[int] = []

    pending_space = False
    seen_content = False

    for index, char in enumerate(text):
        if char in INVISIBLE_CHARACTERS:
            continue

        replacement = CHARACTER_SUBSTITUTIONS.get(char)
        if replacement is None:
            replacement = unicodedata.normalize("NFKC", char)

        if not replacement:  # pragma: no cover - NFKC never empties a character
            continue

        if replacement.isspace() or replacement.strip() == "":
            # Runs of whitespace collapse to a single space, and leading
            # whitespace is dropped. Deferred rather than emitted immediately
            # so trailing whitespace never reaches the output either.
            if seen_content:
                pending_space = True
            continue

        if pending_space:
            out.append(" ")
            offsets.append(index)
            pending_space = False

        for piece in replacement:
            out.append(piece)
            offsets.append(index)
        seen_content = True

    # The extra entry lets an exclusive end index one past the last character
    # resolve without a special case at every call site.
    offsets.append(len(text))

    return NormalisedText(text="".join(out), original=text, offsets=tuple(offsets))
