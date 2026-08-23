"""OCR text cleanup.

The governing constraint: cleanup must never *invent* a vocabulary term the
student did not write. Inflating a score is worse than missing a term, because
the student is then rewarded for the machine's guess.
"""

from __future__ import annotations

import pytest

from app.ocr.postprocess import (
    clean,
    fix_character_confusions,
    join_wrapped_lines,
    rejoin_hyphenated,
    word_count,
)

# ── Hyphenated line breaks ───────────────────────────────────────────────────


def test_rejoins_a_word_split_across_lines() -> None:
    """Left alone, "fluctu-\\nate" is neither word, so the term vanishes."""
    assert rejoin_hyphenated("fluctu-\nate") == "fluctuate"


def test_rejoins_several_breaks() -> None:
    assert rejoin_hyphenated("fluctu-\nate and osc-\nillate") == "fluctuate and oscillate"


def test_rejoins_adjacent_breaks() -> None:
    """Each pass consumes one break, so the rule must run to a fixed point."""
    assert rejoin_hyphenated("in-\ncre-\nase") == "increase"


@pytest.mark.parametrize("dash", ["-", "‐", "‑"])
def test_rejoins_unicode_hyphens(dash: str) -> None:
    assert rejoin_hyphenated(f"fluctu{dash}\nate") == "fluctuate"


def test_leaves_a_real_hyphenated_compound_alone() -> None:
    assert rejoin_hyphenated("well-known figure") == "well-known figure"


def test_a_split_target_term_survives_the_full_pipeline() -> None:
    """The case that directly costs a student vocabulary credit."""
    text = "Output continued to fluctu-\nate throughout the period."
    assert "fluctuate" in clean(text)


# ── Line wrapping ────────────────────────────────────────────────────────────


def test_joins_lines_wrapped_by_the_page_width() -> None:
    text = "The graph shows a\nsteady increase in\noutput."
    assert join_wrapped_lines(text) == "The graph shows a steady increase in output."


def test_keeps_paragraph_breaks() -> None:
    """A blank line is a real break; a single newline is the paper's width."""
    assert join_wrapped_lines("One.\n\nTwo.") == "One.\n\nTwo."


def test_collapses_three_or_more_newlines_to_one_break() -> None:
    assert join_wrapped_lines("One.\n\n\n\nTwo.") == "One.\n\nTwo."


# ── Character confusions ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("l0wer", "lower"), ("s0ared", "soared"), ("0verall", "overall"), ("r0se", "rose")],
)
def test_corrects_zero_read_as_o(raw: str, expected: str) -> None:
    assert fix_character_confusions(raw) == expected


def test_corrects_a_letter_read_as_a_digit_in_a_number() -> None:
    assert fix_character_confusions("2O19") == "2019"


@pytest.mark.parametrize(
    "token", ["COVID19", "Q1", "2019", "30mm", "A4", "MWh", "H2O", "m3", "1st"]
)
def test_leaves_legitimate_mixes_alone(token: str) -> None:
    """A digit run means the token is data, not a misread word."""
    assert fix_character_confusions(token) == token


def test_leaves_an_ambiguous_one_alone() -> None:
    """ "1" is shaped like l, I and i alike.

    Correcting it would swap one non-word for another while risking the wrong
    one. Resolving that needs a lexicon, which this layer does not have.
    """
    assert fix_character_confusions("1ncrease") == "1ncrease"


def test_preserves_case_when_correcting_a_leading_digit() -> None:
    assert fix_character_confusions("0VERALL") == "OVERALL"


def test_correction_never_invents_a_vocabulary_term() -> None:
    """A plain misspelling must not be autocorrected into a scoring term."""
    for misspelling in ["increse", "flucuate", "decreese", "stabel"]:
        assert fix_character_confusions(misspelling) == misspelling


# ── Whitespace and punctuation ───────────────────────────────────────────────


def test_removes_space_before_punctuation() -> None:
    assert clean("The figure rose to 410 MWh .") == "The figure rose to 410 MWh."


def test_adds_a_missing_space_after_punctuation() -> None:
    assert clean("increase,then fall") == "increase, then fall"


def test_collapses_runs_of_spaces() -> None:
    assert clean("a    steady     increase") == "a steady increase"


def test_trims_each_line() -> None:
    assert clean("  One.  \n\n   Two.  ") == "One.\n\nTwo."


# ── Whole pipeline ───────────────────────────────────────────────────────────


def test_empty_input_returns_empty() -> None:
    assert clean("") == ""
    assert clean("   \n\n  ") == ""


def test_realistic_page() -> None:
    raw = (
        "The line graph illustrates the s0lar energy\n"
        "generated between 2019 and 2025 .\n"
        "\n"
        "Overall , output continued to fluctu-\n"
        "ate but r0se substantially."
    )
    cleaned = clean(raw)
    assert cleaned == (
        "The line graph illustrates the solar energy generated between 2019 and 2025.\n\n"
        "Overall, output continued to fluctuate but rose substantially."
    )


def test_word_count() -> None:
    assert word_count("The line graph illustrates a steady increase.") == 7
    assert word_count("") == 0
    # Hyphenated compounds and contractions count once.
    assert word_count("well-known figures didn't fall") == 4
