"""Writing-quality signals."""

from __future__ import annotations

import pytest

from app.nlp.normalise import normalise
from app.nlp.pipeline import get_nlp
from app.nlp.writing import OVERLONG_FLOOR, assess, word_count_adequacy

# ── Word-count adequacy: pure arithmetic, no model needed ────────────────────


@pytest.mark.parametrize("count", [150, 200, 250])
def test_inside_the_band_earns_full_marks(count: int):
    assert word_count_adequacy(count, 150, 250) == 100.0


def test_below_the_band_tapers_proportionally():
    assert word_count_adequacy(75, 150, 250) == 50.0


def test_an_empty_answer_scores_zero():
    assert word_count_adequacy(0, 150, 250) == 0.0


def test_slightly_over_the_band_barely_costs_anything():
    assert word_count_adequacy(260, 150, 250) > 95.0


def test_a_very_long_answer_lands_on_the_floor():
    # Deliberately asymmetric: writing too much is a lesser failure than
    # writing two lines, because the student engaged with the task.
    assert word_count_adequacy(1000, 150, 250) == OVERLONG_FLOOR


def test_the_over_long_taper_never_goes_below_the_floor():
    assert word_count_adequacy(100_000, 150, 250) == OVERLONG_FLOOR


def test_a_short_answer_is_punished_harder_than_a_long_one():
    assert word_count_adequacy(40, 150, 250) < word_count_adequacy(600, 150, 250)


def test_the_band_comes_from_configuration():
    # The rubric is retunable for a study without a redeploy, so the band is
    # not allowed to be a constant in the scoring code.
    assert word_count_adequacy(90, 80, 120) == 100.0


# ── The full assessment ──────────────────────────────────────────────────────


@pytest.fixture
def score():
    def run(text: str, *, target_min: int = 150, target_max: int = 250):
        normalised = normalise(text)
        return assess(get_nlp()(normalised.text), target_min=target_min, target_max=target_max)

    return run


pytestmark_model = pytest.mark.usefixtures("spacy_model")


@pytestmark_model
class TestAssessment:
    def test_a_strong_answer_scores_highly(self, score, strong_answer):
        assert score(strong_answer).score > 85

    def test_a_weak_answer_scores_poorly(self, score, weak_answer):
        assert score(weak_answer).score < 25

    def test_a_two_line_answer_earns_no_free_diversity_marks(self, score, weak_answer):
        # A text too short to repeat itself has a type-token ratio of 1.0. Left
        # unguarded, the shortest and worst answers would score full marks on
        # the component meant to reward vocabulary breadth.
        assert score(weak_answer).lexical_diversity_score < 25

    def test_repetition_is_penalised(self, score):
        repetitive = " ".join(["Sales increased in the year and sales increased again."] * 12)
        assert score(repetitive).lexical_diversity_score < 25

    def test_an_overview_at_the_start_earns_full_marks(self, score):
        result = score("Overall, sales rose. They started at 10 and ended at 90.")
        assert result.has_overview
        assert result.overview_score == 100.0

    def test_an_overview_later_in_the_text_earns_partial_credit(self, score):
        # Summarising is a real skill; it simply belongs at the top. Scoring it
        # zero would teach the student that summarising is wrong.
        result = score(
            "Sales started at 10. They climbed through the middle of the decade. "
            "They ended at 90. In conclusion, the trend was upward throughout."
        )
        assert result.has_overview
        assert 0 < result.overview_score < 100

    def test_no_overview_scores_zero(self, score):
        result = score("Sales started at 10. They ended at 90.")
        assert not result.has_overview
        assert result.overview_score == 0.0

    @pytest.mark.parametrize(
        "cue",
        ["Overall", "In general", "The graph shows", "It is clear that", "The most striking"],
    )
    def test_each_discourse_cue_is_recognised(self, score, cue: str):
        assert score(f"{cue} the figures moved upward across the whole period.").has_overview

    def test_subordinate_clauses_lift_the_structure_score(self, score):
        simple = score("Sales rose. Costs fell. Profit grew. Output climbed. Demand held.")
        complex_ = score(
            "Sales rose steadily while costs fell, which meant that profit grew even "
            "though output climbed only slowly and demand, having held firm, softened."
        )
        assert complex_.sentence_structure_score > simple.sentence_structure_score

    def test_run_on_sentences_are_not_rewarded(self, score):
        run_on = "and then ".join(["sales rose in the following year by a considerable amount"] * 8)
        assert score(run_on).sentence_structure_score < 100

    def test_word_count_ignores_punctuation(self, score):
        assert score("Sales rose, sharply, indeed.").word_count == 4

    def test_sentences_are_counted(self, score):
        assert score("Sales rose. Costs fell. Profit grew.").sentence_count == 3

    def test_the_breakdown_exposes_its_evidence(self, score, strong_answer):
        payload = score(strong_answer).to_dict()
        # The score is a heuristic, so a teacher disputing it must be able to
        # see what it measured.
        assert set(payload["components"]) == {
            "word_count",
            "lexical_diversity",
            "sentence_structure",
            "overview",
        }
        assert payload["measures"]["mattr"] > 0
        assert payload["measures"]["has_overview"] is True

    def test_the_score_is_the_mean_of_its_four_components(self, score, strong_answer):
        result = score(strong_answer)
        expected = (
            result.word_count_score
            + result.lexical_diversity_score
            + result.sentence_structure_score
            + result.overview_score
        ) / 4
        assert result.score == pytest.approx(expected, abs=0.01)

    def test_a_single_word_answer_does_not_crash(self, score):
        result = score("Rose.")
        assert result.word_count == 1
        assert 0 <= result.score <= 100
