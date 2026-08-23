"""Vocabulary detection: lemma matching, phrase matching and masking."""

from __future__ import annotations

import pytest

from app.nlp.detector import detect
from app.nlp.normalise import normalise
from app.nlp.pipeline import get_nlp
from app.nlp.terms import compile_targets, dedupe

pytestmark = pytest.mark.usefixtures("spacy_model")


def run(text: str, terms):
    normalised = normalise(text)
    doc = get_nlp()(normalised.text)
    return detect(doc, normalised, compile_targets(dedupe(list(terms))))


def found(result) -> set[str]:
    return {d.term.term for d in result.detected}


# ── Lemma matching (FR-6.2) ──────────────────────────────────────────────────


@pytest.mark.parametrize("form", ["increase", "increased", "increases", "increasing"])
def test_every_inflection_credits_the_same_term(form: str, term_factory):
    result = run(f"Sales {form} steadily over the period.", [term_factory("increase")])
    assert found(result) == {"increase"}


@pytest.mark.parametrize(
    ("form", "term"),
    [("rose", "rise"), ("fell", "fall"), ("grew", "grow"), ("risen", "rise")],
)
def test_irregular_past_forms_are_lemmatised(form: str, term: str, term_factory):
    result = run(f"Output {form} sharply in 2015.", [term_factory(term)])
    assert found(result) == {term}


def test_a_term_the_lemmatiser_gets_wrong_is_rescued_by_surface_matching(term_factory):
    # spaCy lemmatises "plateaued" to "plateaue". Without the surface-variant
    # fallback the student would score zero for using the word correctly.
    result = run("Prices plateaued after 2018.", [term_factory("plateau")])
    assert found(result) == {"plateau"}


def test_adverb_forms_credit_the_adjective_term(term_factory):
    # Adverbs carry their own lemma, so "steadily" never lemmatises to "steady".
    result = run("The figure rose steadily.", [term_factory("steady", category="stability")])
    assert found(result) == {"steady"}


def test_a_term_the_student_did_not_use_is_missing(term_factory):
    result = run("Sales increased.", [term_factory("increase"), term_factory("fluctuate")])
    assert found(result) == {"increase"}
    assert [t.term for t in result.missing] == ["fluctuate"]


def test_matching_is_case_insensitive(term_factory):
    result = run("Increases were recorded across the board.", [term_factory("increase")])
    assert found(result) == {"increase"}


@pytest.mark.parametrize(
    ("text", "term", "category"),
    [
        ("There was considerable fluctuation.", "fluctuate", "fluctuation"),
        ("Sharp fluctuations were recorded.", "fluctuate", "fluctuation"),
        ("A steady reduction followed.", "reduce", "decrease"),
        ("The chart shows strong growth.", "grow", "increase"),
        ("There was little variation.", "vary", "fluctuation"),
        ("Stability returned after 2015.", "stable", "stability"),
    ],
)
def test_noun_derivations_credit_the_verb_or_adjective_term(
    text: str, term: str, category: str, term_factory
):
    # "fluctuation" is its own lemma, not an inflection of "fluctuate", so
    # neither lemma matching nor inflection reaches it. Graph description leans
    # on these noun forms constantly.
    result = run(text, [term_factory(term, category=category)])
    assert found(result) == {term}


def test_a_substring_of_a_longer_word_is_not_a_match(term_factory):
    # A regex for "rise" would match inside "surprise"; token-based matching
    # cannot.
    result = run("The result was a surprise to everyone.", [term_factory("rise")])
    assert found(result) == set()


def test_a_function_word_homograph_is_not_credited(term_factory):
    # "Out" as a bare preposition is not the term "bottom out", and a
    # single-word term is only credited in a content-word role.
    result = run("They looked out of the window.", [term_factory("out")])
    assert found(result) == set()


# ── Phrase matching (FR-6.3) ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "term", "lemma"),
    [
        ("Revenue was higher than expected.", "higher than", "high than"),
        ("Costs were lower than revenue.", "lower than", "low than"),
        ("Compared with 2018, output fell.", "compared with", "compare with"),
        ("It reached the highest point in May.", "highest point", "high point"),
        ("The lowest point was in June.", "lowest point", "low point"),
        ("The line bottomed out in March.", "bottom out", "bottom out"),
        ("In contrast to imports, exports rose.", "in contrast to", "in contrast to"),
        ("Profits reached a maximum of 40.", "reach a maximum", "reach a maximum"),
    ],
)
def test_phrases_match_across_inflection(text: str, term: str, lemma: str, term_factory):
    result = run(text, [term_factory(term, lemma, is_phrase=True)])
    assert found(result) == {term}


def test_a_phrase_split_across_a_line_break_still_matches(term_factory):
    result = run("Revenue was higher\n   than costs.", [term_factory("higher than", "high than")])
    assert found(result) == {"higher than"}


def test_phrase_masking_prevents_double_counting(term_factory):
    # Without masking, "highest point" would also register a "high" detection,
    # counting one piece of student writing as two vocabulary hits.
    result = run(
        "It reached its highest point in May.",
        [term_factory("highest point", "high point"), term_factory("high", category="peak")],
    )
    assert found(result) == {"highest point"}


def test_the_longer_phrase_wins_an_overlap(term_factory):
    result = run(
        "The lowest point was in June.",
        [
            term_factory("lowest point", "low point"),
            term_factory("point", category="peak"),
        ],
    )
    assert found(result) == {"lowest point"}


def test_a_masked_word_is_still_credited_where_it_stands_alone(term_factory):
    result = run(
        "It reached its highest point in May, and that point was the peak.",
        [term_factory("highest point", "high point"), term_factory("peak", category="peak")],
    )
    assert found(result) == {"highest point", "peak"}


# ── Counting (FR-6.4) ────────────────────────────────────────────────────────


def test_repeats_are_counted_but_the_term_is_unique(term_factory):
    result = run(
        "Sales increased in 2011, increased again in 2012 and increased in 2013.",
        [term_factory("increase")],
    )
    assert result.unique_terms == 1
    assert result.total_occurrences == 3
    assert result.detected[0].count == 3


def test_matched_forms_report_the_students_own_spelling(term_factory):
    result = run("Sales increased and were still increasing in 2013.", [term_factory("increase")])
    assert result.detected[0].matched_forms == ["increased", "increasing"]


def test_positions_index_the_original_text(term_factory):
    text = "Overall, sales rose sharply."
    result = run(text, [term_factory("rise")])
    start, end = result.detected[0].occurrences[0].start, result.detected[0].occurrences[0].end
    assert text[start:end] == "rose"


def test_positions_survive_normalisation(term_factory):
    text = "Overall,  sales  “rose”  sharply."
    result = run(text, [term_factory("rise")])
    start, end = result.detected[0].occurrences[0].start, result.detected[0].occurrences[0].end
    assert text[start:end] == "rose"


def test_detections_are_ordered_by_first_appearance(term_factory):
    result = run(
        "Sales fell, then increased, then fluctuated.",
        [term_factory("increase"), term_factory("fall"), term_factory("fluctuate")],
    )
    assert [d.term.term for d in result.detected] == ["fall", "increase", "fluctuate"]


def test_empty_target_set_detects_nothing():
    result = run("Sales increased sharply.", [])
    assert result.detected == []
    assert result.missing == []


def test_serialised_detection_carries_everything_the_ui_needs(term_factory):
    result = run("Sales increased sharply.", [term_factory("increase")])
    payload = result.detected[0].to_dict()
    assert payload["term"] == "increase"
    assert payload["category"] == "increase"
    assert payload["count"] == 1
    assert payload["matched_forms"] == ["increased"]
    assert payload["positions"] == [[6, 15]]
