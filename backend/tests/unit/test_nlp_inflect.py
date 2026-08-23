"""Surface-variant generation — the safety net under lemma matching."""

from __future__ import annotations

import pytest

from app.nlp.inflect import phrase_variants, surface_variants


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("increase", "increased"),
        ("increase", "increasing"),
        ("increase", "increases"),
        ("climb", "climbed"),
        ("climb", "climbing"),
        ("drop", "dropped"),  # consonant doubling
        ("drop", "dropping"),
        ("vary", "varies"),  # y -> ies
        ("vary", "varied"),
        ("vary", "varying"),
        ("steady", "steadily"),  # adverb: the lemmatiser gives adverbs their own lemma
        ("plateau", "plateaued"),  # the lemmatiser produces "plateaue" for this
        ("plateau", "plateaus"),
        ("plateau", "plateauing"),
        ("stable", "stably"),
        ("fluctuate", "fluctuated"),
        ("fluctuate", "fluctuating"),
        ("high", "higher"),
        ("high", "highest"),
        ("low", "lower"),
    ],
)
def test_expected_inflection_is_generated(word: str, expected: str):
    assert expected in surface_variants(word)


def test_the_word_itself_is_included():
    assert "surge" in surface_variants("surge")


def test_generation_is_lower_cased():
    assert all(v == v.lower() for v in surface_variants("Increase"))


def test_uppercase_input_still_matches_the_base_form():
    assert "increase" in surface_variants("INCREASE")


def test_long_adjectives_get_no_comparative():
    # English uses "more constant", and generating "constanter" is pointless.
    variants = surface_variants("considerable")
    assert "considerabler" not in variants


def test_non_alphabetic_input_is_returned_unchanged():
    assert surface_variants("2019") == {"2019"}


def test_empty_input_yields_nothing():
    assert surface_variants("   ") == set()


def test_phrase_inflects_only_the_first_word():
    variants = phrase_variants("bottom out")
    assert ("bottomed", "out") in variants
    assert ("bottoming", "out") in variants
    # The particle is fixed; inflecting it would generate combinations English
    # does not produce.
    assert not any(v[1] != "out" for v in variants)


def test_phrase_keeps_its_own_form():
    assert ("compared", "with") in phrase_variants("compared with")


def test_three_word_phrase_keeps_its_tail():
    variants = phrase_variants("reach a maximum")
    assert ("reached", "a", "maximum") in variants
    assert ("reach", "a", "maximum") in variants


def test_single_word_phrase_behaves_like_a_word():
    assert ("peaked",) in phrase_variants("peak")


def test_empty_phrase_yields_nothing():
    assert phrase_variants("  ") == set()


def test_doubling_generates_both_spellings():
    # The consonant-doubling rule is an approximation. Generating both means an
    # uncertain call costs a harmless non-word rather than a student's marks.
    variants = surface_variants("drop")
    assert {"dropped", "droped"} <= variants
