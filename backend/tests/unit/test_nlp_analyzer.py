"""The analysis entry point: guards, output shape and determinism."""

from __future__ import annotations

import pytest

from app.core.exceptions import AnalysisError
from app.nlp import MAX_ANALYSIS_CHARS
from app.nlp.analyzer import analyse
from app.nlp.terms import clear_cache, compile_targets

pytestmark = pytest.mark.usefixtures("spacy_model")


@pytest.fixture
def targets(term_factory):
    return [
        term_factory("increase"),
        term_factory("fall", category="decrease"),
        term_factory("fluctuate", category="fluctuation"),
        term_factory("higher than", "high than", category="comparison"),
    ]


# ── Guards ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("text", ["", "   ", "\n\t  \n"])
def test_an_empty_answer_is_refused(text: str, targets):
    with pytest.raises(AnalysisError):
        analyse(text, targets)


def test_an_answer_of_only_invisible_characters_is_refused(targets):
    # Scoring this zero would be a judgement about writing, and there is none.
    with pytest.raises(AnalysisError):
        analyse("​​​", targets)


def test_an_over_long_answer_is_refused(targets):
    with pytest.raises(AnalysisError) as exc:
        analyse("word " * (MAX_ANALYSIS_CHARS // 2), targets)
    assert "limit" in exc.value.message


def test_an_answer_at_the_limit_is_accepted(targets):
    assert analyse("sales increased. " * 100, targets).word_count > 0


def test_no_required_targets_scores_zero_rather_than_dividing_by_zero(term_factory):
    result = analyse("Sales increased.", [term_factory("increase", is_required=False)])
    assert result.score.vocabulary_percentage == 0.0
    assert result.score.total_target_count == 0


def test_an_empty_target_set_does_not_crash():
    result = analyse("Sales increased sharply over the period.", [])
    assert result.score.vocabulary_percentage == 0.0
    assert result.word_count > 0


# ── Output shape ─────────────────────────────────────────────────────────────


def test_score_fields_cover_every_column(targets, strong_answer):
    fields = analyse(strong_answer, targets).to_score_fields()
    assert set(fields) == {
        "vocabulary_score",
        "writing_score",
        "final_score",
        "vocabulary_percentage",
        "detected_count",
        "unique_detected_count",
        "total_target_count",
        "detected_terms",
        "missing_terms",
        "category_breakdown",
        "writing_breakdown",
        "reward_tier",
        "feedback",
        "engine_version",
    }


def test_score_fields_are_json_serialisable(targets, strong_answer):
    import json

    # They are written to JSON columns, so anything that cannot round-trip
    # fails at INSERT rather than here.
    fields = analyse(strong_answer, targets).to_score_fields()
    assert json.loads(json.dumps(fields))["engine_version"] == fields["engine_version"]


def test_missing_terms_record_whether_they_were_required(term_factory):
    targets = [term_factory("increase"), term_factory("soar", is_required=False)]
    fields = analyse("Costs held level.", targets).to_score_fields()
    required = {m["term"]: m["is_required"] for m in fields["missing_terms"]}
    assert required == {"increase": True, "soar": False}


def test_the_engine_version_is_stamped(targets, strong_answer):
    assert analyse(strong_answer, targets).to_score_fields()["engine_version"]


def test_word_count_matches_the_writing_assessment(targets, strong_answer):
    result = analyse(strong_answer, targets)
    assert result.word_count == result.writing.word_count


# ── Determinism ──────────────────────────────────────────────────────────────


def test_the_same_answer_scores_identically_twice(targets, strong_answer):
    # An academic evaluation depends on reproducibility, which is the first
    # reason feedback is templated rather than generated.
    first = analyse(strong_answer, targets).to_score_fields()
    second = analyse(strong_answer, targets).to_score_fields()
    assert first == second


def test_duplicate_targets_do_not_inflate_the_denominator(term_factory):
    duplicated = [term_factory("increase"), term_factory("increase"), term_factory("rise")]
    assert analyse("Sales increased.", duplicated).score.total_target_count == 2


def test_compiled_targets_are_reused_for_the_same_set(term_factory):
    clear_cache()
    terms = (term_factory("increase"), term_factory("rise"))
    assert compile_targets(terms) is compile_targets(list(terms))


def test_a_different_target_set_compiles_separately(term_factory):
    one = compile_targets([term_factory("increase")])
    two = compile_targets([term_factory("decrease", category="decrease")])
    assert one is not two
