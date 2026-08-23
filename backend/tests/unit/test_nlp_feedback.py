"""Feedback generation — including the tone rules, which are requirements."""

from __future__ import annotations

import pytest

from app.models.enums import Gender, GraphType, RewardTier
from app.nlp.analyzer import analyse
from app.nlp.feedback import HAMMER_ENCOURAGEMENT

pytestmark = pytest.mark.usefixtures("spacy_model")


@pytest.fixture
def targets(term_factory):
    return [
        term_factory("increase"),
        term_factory("rise"),
        term_factory("surge", weight=1.25),
        term_factory("decrease", category="decrease"),
        term_factory("fall", category="decrease"),
        term_factory("fluctuate", category="fluctuation", weight=1.5),
        term_factory("stable", category="stability"),
        term_factory("peak", category="peak"),
        term_factory("higher than", "high than", category="comparison"),
        term_factory("bottom out", category="lowest"),
    ]


# ── The hammer tier must never humiliate ─────────────────────────────────────


def test_the_hammer_tier_always_carries_the_encouragement(targets, weak_answer):
    result = analyse(weak_answer, targets)
    assert result.score.reward_tier is RewardTier.HAMMER
    assert HAMMER_ENCOURAGEMENT in result.feedback["message"]


def test_the_encouragement_comes_before_the_number(targets, weak_answer):
    # A student reading a low score first has often stopped reading by the time
    # the support arrives.
    message = analyse(weak_answer, targets).feedback["message"]
    assert message.index(HAMMER_ENCOURAGEMENT) < message.index("You used")


def test_the_hammer_tier_still_names_a_strength(targets, weak_answer):
    assert analyse(weak_answer, targets).feedback["strengths"]


def test_even_a_zero_scoring_answer_gets_an_honest_strength(targets):
    result = analyse("qqq zzz.", targets)
    assert result.score.unique_detected_count == 0
    assert len(result.feedback["strengths"]) == 1


def test_the_hammer_next_step_is_actionable(targets, weak_answer):
    assert "vocabulary library" in analyse(weak_answer, targets).feedback["next_step"]


# ── Headlines ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("gender", "headline"), [(Gender.MALE, "Graph King"), (Gender.FEMALE, "Graph Queen")]
)
def test_the_crown_headline_is_gendered(term_factory, gender: Gender, headline: str):
    result = analyse("Sales increased.", [term_factory("increase")], gender=gender)
    assert result.score.reward_tier is RewardTier.CROWN
    assert result.feedback["headline"] == headline


def test_the_crown_headline_falls_back_when_gender_is_unknown(term_factory):
    result = analyse("Sales increased.", [term_factory("increase")])
    assert result.feedback["headline"] == "Graph Champion"


@pytest.mark.parametrize(
    ("text", "headline"),
    [("The graph go up.", "Keep Practicing!")],
)
def test_tier_headlines(term_factory, targets, text: str, headline: str):
    assert analyse(text, targets).feedback["headline"] == headline


# ── Naming the words, not scolding ───────────────────────────────────────────


def test_improvements_name_the_specific_words_to_try(targets):
    improvements = analyse("Sales increased sharply.", targets).feedback["improvements"]
    assert improvements
    assert any("'" in line for line in improvements)


def test_a_category_the_student_used_is_not_reported_as_absent(term_factory):
    # Telling a student they used "no increase language" when they wrote
    # "increased" is the fastest way to lose their trust in the feedback.
    targets = [term_factory("increase"), term_factory("rise"), term_factory("surge")]
    improvements = analyse("Sales increased sharply.", targets).feedback["improvements"]
    assert not any("No increase language" in line for line in improvements)
    assert any("Widen the increase language" in line for line in improvements)


def test_an_untouched_category_is_reported_as_absent(targets):
    improvements = analyse("Sales increased sharply.", targets).feedback["improvements"]
    assert any(line.startswith("No ") for line in improvements)


def test_untouched_categories_are_suggested_before_partly_used_ones(targets):
    improvements = analyse("Sales increased sharply.", targets).feedback["improvements"]
    absent = [i for i, line in enumerate(improvements) if line.startswith("No ")]
    widen = [i for i, line in enumerate(improvements) if line.startswith("Widen ")]
    assert not widen or (absent and max(absent) < min(widen))


def test_the_most_basic_missing_term_is_suggested_first(term_factory):
    targets = [
        term_factory("plummet", category="decrease", weight=1.5),
        term_factory("fall", category="decrease", weight=1.0),
        term_factory("increase"),
    ]
    # Advice a struggling student cannot act on is not advice.
    improvements = analyse("Sales increased.", targets).feedback["improvements"]
    decrease_line = next(line for line in improvements if "decrease language" in line)
    assert decrease_line.index("'fall'") < decrease_line.index("'plummet'")


def test_suggestions_are_capped(targets):
    assert len(analyse("Nothing relevant here at all.", targets).feedback["improvements"]) <= 3


def test_strengths_are_capped(targets, strong_answer):
    assert len(analyse(strong_answer, targets).feedback["strengths"]) <= 4


def test_missing_by_category_excludes_bonus_terms(term_factory):
    # A bonus term was never asked for, so listing it as missed would report a
    # failure that did not happen.
    targets = [term_factory("increase"), term_factory("soar", is_required=False)]
    feedback = analyse("Costs held level.", targets).feedback
    assert feedback["missing_by_category"] == {"increase": ["increase"]}


def test_a_missing_overview_is_suggested(targets):
    improvements = analyse("Sales increased. Costs fell.", targets).feedback["improvements"]
    assert any("overview" in line for line in improvements)


def test_a_short_answer_is_told_to_write_more(targets, weak_answer):
    improvements = analyse(weak_answer, targets).feedback["improvements"]
    assert any("Write more" in line for line in improvements) or len(improvements) == 3


def test_bonus_terms_are_acknowledged_in_the_message(term_factory):
    targets = [term_factory("increase"), term_factory("soar", is_required=False)]
    message = analyse("Sales increased and then soared.", targets).feedback["message"]
    assert "bonus term" in message


def test_the_next_step_names_the_chart_type(targets):
    result = analyse(
        "Overall sales increased and then fell back a little in the final year.",
        targets,
        graph_type=GraphType.BAR,
    )
    if result.score.reward_tier in (RewardTier.FLOWER, RewardTier.STEADY):
        assert "bar" in result.feedback["next_step"]


def test_strengths_never_claim_vocabulary_that_was_not_used(targets):
    # Templated feedback exists precisely so praise cannot be hallucinated.
    result = analyse("Sales increased sharply in every single year.", targets)
    used = {form for d in result.detection.detected for form in d.matched_forms}
    for line in result.feedback["strengths"]:
        if "language:" in line:
            quoted = line.split("language:", 1)[1]
            for word in (w.strip() for w in quoted.split(",")):
                assert word in used


def test_feedback_carries_every_documented_key(targets, strong_answer):
    feedback = analyse(strong_answer, targets).feedback
    assert set(feedback) == {
        "headline",
        "message",
        "strengths",
        "improvements",
        "missing_by_category",
        "next_step",
    }
