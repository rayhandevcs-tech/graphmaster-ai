"""OCR text cleanup (07-ocr-architecture.md §4.3).

Deliberately restrained. Aggressive autocorrection risks *inventing* a
vocabulary term the student never wrote, which inflates the score — a worse
failure than missing one, because the student is then rewarded for the
machine's guess. Every rule here either removes an artefact of the paper (line
breaks, hyphenation) or fixes a character-shape confusion that cannot plausibly
create a new word.
"""

from __future__ import annotations

import re

# A line ending in a hyphen is a word split across two lines. Rejoining matters
# for scoring: "fluctu-\nate" left alone is neither "fluctu" nor "fluctuate",
# so a targeted term simply vanishes from the analysis.
HYPHEN_BREAK = re.compile(r"(\w+)[-‐‑]\s*\n\s*(\w+)")

# A newline that is not a paragraph break is an artefact of the page width, not
# a sentence boundary. Two or more newlines are treated as a real break.
SINGLE_NEWLINE = re.compile(r"(?<!\n)\n(?!\n)")
MULTI_NEWLINE = re.compile(r"\n{2,}")
HORIZONTAL_SPACE = re.compile(r"[^\S\n]+")

# Space before punctuation is an OCR artefact; after it is correct.
SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?%])")
MISSING_SPACE_AFTER_PUNCT = re.compile(r"([,.;:!?])([A-Za-z])")

# Only "0" is mapped back to a letter. "1" is deliberately absent: it is
# equally shaped like "l", "I" and "i", so "1ncrease" could be corrected to
# "lncrease" as readily as to "increase" — swapping one non-word for another
# while risking a wrong one. Resolving that needs a lexicon, which the analyser
# has and this layer does not, so the ambiguous case is left alone.
DIGIT_TO_LETTER = {"0": "o"}
# The numeric direction is safe in both cases, because a surrounding run of
# digits already says the token is a number.
LETTER_TO_DIGIT = {"O": "0", "o": "0", "l": "1", "I": "1"}

TOKEN = re.compile(r"\S+")
# Two or more consecutive digits read as data — a year, a quantity, a figure —
# not as a misread letter.
DIGIT_RUN = re.compile(r"\d{2,}")


def rejoin_hyphenated(text: str) -> str:
    """Rejoin words split across a line break by a trailing hyphen."""
    # Repeated until stable: two hyphenated breaks can be adjacent, and each
    # pass consumes only one.
    previous = None
    while previous != text:
        previous = text
        text = HYPHEN_BREAK.sub(r"\1\2", text)
    return text


def join_wrapped_lines(text: str) -> str:
    """Collapse single line breaks, keeping blank-line paragraph breaks."""
    # Paragraph breaks are parked behind a sentinel so the single-newline rule
    # cannot eat them, then restored.
    sentinel = "\x00PARA\x00"
    text = MULTI_NEWLINE.sub(sentinel, text)
    text = SINGLE_NEWLINE.sub(" ", text)
    return text.replace(sentinel, "\n\n")


def fix_character_confusions(text: str) -> str:
    """Repair digit/letter shape confusions inside single tokens.

    Applied per token and only when the token's own shape makes the intent
    unambiguous:

    * A mostly-alphabetic token with one or two isolated "0"s is a misread "o" —
      "l0wer" → "lower", "s0ared" → "soared".
    * A mostly-numeric token with one stray letter is a misread digit —
      "2O19" → "2019".

    In the alphabetic direction a token containing a *run* of two or more
    digits is left alone. That is what protects "COVID19", "30mm" and every
    other legitimate mix of letters and numbers from being corrupted into a
    word. The numeric direction needs no such guard, since a digit run there is
    the very evidence that the token is a number.
    """

    def fix_token(match: re.Match[str]) -> str:
        token = match.group(0)
        letters = sum(c.isalpha() for c in token)
        digits = sum(c.isdigit() for c in token)

        if digits == 0 or letters == 0:
            return token

        if letters >= 3 and digits <= 2 and not DIGIT_RUN.search(token):
            candidate = "".join(DIGIT_TO_LETTER.get(c, c) for c in token)
            # Match the token's own case: a "0" opening a capitalised word is a
            # capital O, not a lowercase o.
            if token[0].isdigit() and len(token) > 1 and token[1].isupper():
                candidate = candidate[0].upper() + candidate[1:]
            return candidate

        if digits >= 2 and letters == 1:
            return "".join(LETTER_TO_DIGIT.get(c, c) for c in token)

        return token

    return TOKEN.sub(fix_token, text)


def normalise_whitespace(text: str) -> str:
    text = HORIZONTAL_SPACE.sub(" ", text)
    text = SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = MISSING_SPACE_AFTER_PUNCT.sub(r"\1 \2", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def clean(text: str) -> str:
    """Run the full cleanup pipeline in dependency order."""
    if not text or not text.strip():
        return ""

    # Hyphen rejoining must precede line joining: once the newline is a space,
    # the trailing hyphen is no longer distinguishable from a real one.
    text = rejoin_hyphenated(text)
    text = join_wrapped_lines(text)
    text = fix_character_confusions(text)
    return normalise_whitespace(text)


def word_count(text: str) -> int:
    """Words in a cleaned answer, for the length feedback in §NFR and FR-8."""
    return len(re.findall(r"\b[\w'-]+\b", text))
