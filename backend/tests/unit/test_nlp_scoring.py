"""Score assembly, reward tiers and engine versioning."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.models.enums import RewardTier
from app.nlp import ENGINE_VERSION
from app.nlp.analyzer import analyse
from app.nlp.scoring import engine_version, reward_tier, rubric

# ── Reward tiers (FR-7.1): pure, no model needed ─────────────────────────────


@pytest.mark.parametrize(
    ("percentage", "tier"),
    [
        (100.0, RewardTier.CROWN),
        (90.0, RewardTier.CROWN),
        (89.99, RewardTier.FLOWER),
        (75.0, RewardTier.FLOWER),
        (60.0, RewardTier.FLOWER),
        (59.99, RewardTier.STEADY),
        (55.0, RewardTier.STEADY),
        (50.0, RewardTier.STEADY),
        (49.99, RewardTier.HAMMER),
        (0.0, RewardTier.HAMMER),
    ],
)
def test_tier_boundaries(percentage: float, tier: RewardTier):
    assert reward_tier(percentage, get_settings()) is tier


def test_the_fifty_to_fifty_nine_band_is_not_a_hammer():
    # The specification leaves 50–59% in no band. Dropping a comedy hammer on a
    # student who scored 59% works against the never-humiliate rule, so the
    # steady tier fills the gap (PROJECT_PLAN §3.1).
    assert reward_tier(55.0, get_settings()) is RewardTier.STEADY


def test_tier_thresholds_come_from_configuration():
    tuned = get_settings().model_copy(update={"TIER_CROWN_MIN": 95.0})
    assert reward_tier(92.0, tuned) is RewardTier.FLOWER


# ── Engine version ───────────────────────────────────────────────────────────


def test_engine_version_starts_with_the_code_version():
    assert engine_version(get_settings()).startswith(f"{ENGINE_VERSION}+")


def test_engine_version_fits_the_column():
    assert len(engine_version(get_settings())) <= 32


def test_engine_version_is_stable_for_the_same_rubric():
    settings = get_settings()
    assert engine_version(settings) == engine_version(settings)


@pytest.mark.parametrize(
    "change",
    [
        {"VOCABULARY_WEIGHT": 0.6, "WRITING_WEIGHT": 0.4},
        {"TIER_CROWN_MIN": 95.0},
        {"TIER_FLOWER_MIN": 65.0},
        {"TARGET_WORD_COUNT_MIN": 120},
        {"TARGET_WORD_COUNT_MAX": 300},
    ],
)
def test_a_retuned_rubric_changes_the_engine_version(change: dict):
    # Weights are deployment configuration precisely so a study can retune them
    # without a redeploy. Without the fingerprint, two incomparable scores would
    # carry the same version and silently corrupt the cohort comparison the
    # field exists to protect.
    base = get_settings()
    assert engine_version(base.model_copy(update=change)) != engine_version(base)


def test_rubric_reports_the_deployed_configuration():
    settings = get_settings()
    published = rubric(settings)
    assert published["vocabulary_weight"] == settings.VOCABULARY_WEIGHT
    assert published["writing_weight"] == settings.WRITING_WEIGHT
    assert published["tier_thresholds"]["crown"] == settings.TIER_CROWN_MIN
    assert published["target_word_count"]["min"] == settings.TARGET_WORD_COUNT_MIN


# ── Score assembly ───────────────────────────────────────────────────────────


@pytest.fixture
def ten_targets(term_factory):
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


@pytest.mark.usefixtures("spacy_model")
class TestScoreAssembly:
    def test_percentage_is_unique_terms_over_required_targets(self, ten_targets):
        result = analyse("Sales increased, then decreased, then fluctuated.", ten_targets)
        assert result.score.unique_detected_count == 3
        assert result.score.total_target_count == 10
        assert result.score.vocabulary_percentage == 30.0

    def test_repeating_one_term_does_not_raise_the_percentage(self, ten_targets):
        once = analyse("Sales increased.", ten_targets)
        eight_times = analyse(
            "Sales increased and increased and increased and increased and "
            "increased and increased and increased and increased.",
            ten_targets,
        )
        # Counting occurrences would reward writing "increase" eight times over
        # using eight different terms — the opposite of the vocabulary range
        # the platform exists to teach.
        assert eight_times.score.vocabulary_percentage == once.score.vocabulary_percentage
        assert eight_times.score.detected_count > once.score.detected_count

    def test_weight_has_no_effect_on_the_score(self, term_factory):
        """The whole reason the field is being renamed in the interface.

        A teacher reading a column headed "Weight" reasonably concludes it
        moves the mark. It does not: the vocabulary percentage is an unweighted
        count of unique required terms used (FR-6.6), so a term set to 9.99 and
        one set to 0.01 are worth exactly the same. If someone later wires
        weight into ``scoring.py``, this fails — which is the point, because
        every historical score would silently stop being comparable.
        """
        flat = [
            term_factory("increase"),
            term_factory("decrease", category="decrease"),
        ]
        lopsided = [
            term_factory("increase", weight=9.99),
            term_factory("decrease", category="decrease", weight=0.01),
        ]
        answer = "Sales increased over the period."

        light = analyse(answer, lopsided)
        even = analyse(answer, flat)

        assert light.score.vocabulary_percentage == even.score.vocabulary_percentage == 50.0
        assert light.score.final_score == even.score.final_score
        assert light.score.reward_tier is even.score.reward_tier

    def test_optional_terms_are_credited_but_not_counted_in_the_denominator(self, term_factory):
        targets = [
            term_factory("increase"),
            term_factory("decrease", category="decrease"),
            term_factory("soar", is_required=False, weight=1.5),
        ]
        result = analyse("Sales increased and then soared.", targets)
        assert result.score.total_target_count == 2
        assert result.score.bonus_terms_used == 1
        # Two unique terms found against a denominator of two.
        assert result.score.vocabulary_percentage == 100.0

    def test_bonus_terms_cannot_push_the_percentage_past_one_hundred(self, term_factory):
        targets = [
            term_factory("increase"),
            term_factory("rise", is_required=False),
            term_factory("surge", is_required=False),
            term_factory("climb", is_required=False),
        ]
        result = analyse("Sales increased, rose, surged and climbed.", targets)
        assert result.score.vocabulary_percentage == 100.0

    def test_final_score_is_seventy_thirty(self, ten_targets, strong_answer):
        settings = get_settings()
        result = analyse(strong_answer, ten_targets)
        expected = (
            settings.VOCABULARY_WEIGHT * result.score.vocabulary_score
            + settings.WRITING_WEIGHT * result.score.writing_score
        )
        assert result.score.final_score == pytest.approx(expected, abs=0.01)

    def test_the_tier_follows_vocabulary_not_the_final_score(self, term_factory):
        # Two target terms, both used, in an answer whose writing score is
        # dreadful. The vocabulary percentage is 100, so the tier is a crown
        # even though the final score is nowhere near 90.
        targets = [term_factory("increase"), term_factory("fall", category="decrease")]
        result = analyse("It increase. It fall.", targets)
        assert result.score.vocabulary_percentage == 100.0
        assert result.score.reward_tier is RewardTier.CROWN
        assert result.score.final_score < 90

    def test_scores_stay_inside_the_column_constraints(self, ten_targets, strong_answer):
        fields = analyse(strong_answer, ten_targets).to_score_fields()
        for key in ("vocabulary_score", "writing_score", "final_score"):
            assert 0 <= fields[key] <= 100

    def test_category_breakdown_covers_every_category(self, ten_targets):
        result = analyse("Sales increased and then fluctuated.", ten_targets)
        breakdown = result.categories
        assert breakdown["increase"]["detected"] == ["increase"]
        assert breakdown["increase"]["target_count"] == 3
        assert breakdown["fluctuation"]["percentage"] == 100.0
        assert breakdown["decrease"]["detected"] == []
        assert set(breakdown["decrease"]["missing"]) == {"decrease", "fall"}

    def test_category_breakdown_is_ordered_for_a_stable_diff(self, ten_targets):
        result = analyse("Sales increased.", ten_targets)
        assert list(result.categories) == sorted(result.categories)
