"""Normalisation and offset mapping."""

from __future__ import annotations

import pytest

from app.nlp.normalise import normalise


def test_typographic_quotes_become_ascii():
    assert normalise("the “graph” shows").text == 'the "graph" shows'


def test_typographic_apostrophe_becomes_ascii():
    assert normalise("it’s rising").text == "it's rising"


@pytest.mark.parametrize("dash", ["–", "—", "‒", "−", "‐"])
def test_every_dash_variant_becomes_a_hyphen(dash: str):
    assert normalise(f"bottom{dash}out").text == "bottom-out"


def test_non_breaking_space_becomes_a_space():
    assert normalise("higher than").text == "higher than"


def test_zero_width_space_is_removed():
    # Left in place it silently prevents the word ever matching a term, and
    # the student cannot see it to fix it.
    assert normalise("in​crease").text == "increase"


def test_whitespace_runs_collapse():
    assert normalise("sales   rose\n\n  sharply").text == "sales rose sharply"


def test_leading_and_trailing_whitespace_are_dropped():
    assert normalise("   rose   ").text == "rose"


def test_case_is_preserved():
    # Lowercasing here would degrade the POS tagger, which is what stops a
    # homograph in a function-word role being counted (see the module docstring).
    assert normalise("Sales Rose").text == "Sales Rose"


def test_punctuation_is_preserved():
    assert normalise("rose, then fell.").text == "rose, then fell."


def test_empty_input():
    result = normalise("")
    assert result.text == ""
    assert result.to_original(0, 0) == (0, 0)


def test_whitespace_only_input():
    assert normalise("   \n\t ").text == ""


def test_offsets_survive_collapsed_whitespace():
    original = "sales    rose sharply"
    result = normalise(original)
    start = result.text.index("rose")
    assert result.original_slice(start, start + 4) == "rose"


def test_offsets_survive_removed_zero_width_characters():
    original = "the fig​ure climbed"
    result = normalise(original)
    start = result.text.index("climbed")
    assert result.original_slice(start, start + 7) == "climbed"


def test_offsets_survive_substituted_characters():
    original = "it “rose” quickly"
    result = normalise(original)
    start = result.text.index("rose")
    assert result.original_slice(start, start + 4) == "rose"


def test_end_offset_is_exclusive_and_excludes_the_following_space():
    # A regression: reading the end straight out of the map returns where the
    # *next* character came from, which after a collapsed whitespace run drags
    # the highlight over the space.
    original = "sales   rose   sharply"
    result = normalise(original)
    start = result.text.index("rose")
    assert result.original_slice(start, start + 4) == "rose"


def test_offsets_are_one_longer_than_the_text():
    result = normalise("rose")
    assert len(result.offsets) == len(result.text) + 1


def test_out_of_range_span_is_clamped_not_raised():
    result = normalise("rose")
    assert result.to_original(-5, 900) == (0, 4)


def test_reversed_span_collapses_to_a_point():
    result = normalise("rose sharply")
    assert result.to_original(6, 2) == (6, 6)


def test_original_is_kept_verbatim():
    original = "  the “graph”  "
    assert normalise(original).original == original
