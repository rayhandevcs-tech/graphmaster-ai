"""The comparison layer: gates, baselines, distributions and self-overlap.

Pure functions over rows the repository has already read, so none of this
needs a database. That is the dividend of keeping the comparison out of the
analyzer: the arithmetic that decides what a teacher sees can be exercised
exhaustively, in milliseconds, against inputs a real corpus would take a term
to produce.

What is being protected here is mostly *restraint*. Several of these tests
assert that something is absent — no verdict, no ordering, no zero standing in
for a missing measurement — because those are the failures that would not
announce themselves.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

from app.assessment.analyzers.writing_profile import MEASURES
from app.assessment.consistency import (
    COMPARED_MEASURES,
    CONSISTENCY_MODEL_VERSION,
    ConsistencyDisabledError,
    Profile,
    ProfileRow,
    baseline,
    class_distribution,
    comparable,
    compare_student,
    partition,
    require_enabled,
    segments,
    self_overlap,
)
from app.assessment.consistency.gating import REASONS
from app.core.config import Settings

EPOCH = dt.datetime(2026, 3, 1, 9, 0, tzinfo=dt.UTC)

BASE_MEASURES = {
    "lexical_diversity": 0.72,
    "mean_sentence_length": 18.0,
    "sentence_length_variation": 5.0,
    "subordination_ratio": 0.30,
    "vocabulary_coverage": 60.0,
}

STUDENT = uuid.uuid4()


def row(
    *,
    minutes: int = 0,
    user_id: uuid.UUID | None = None,
    graph_type: str = "line",
    input_method: str = "typed",
    assessment_version: str = "1.0.0+abcd1234",
    profile_: Profile | None = ...,  # type: ignore[assignment]
    word_count: int = 200,
    spelling_score: float | None = 88.0,
    grammar_score: float | None = None,
    **measures,
) -> ProfileRow:
    """One assessed submission, with sensible defaults for everything a gate reads."""
    if profile_ is ...:
        profile_ = Profile(
            measures={**BASE_MEASURES, **measures},
            word_count=word_count,
            sentence_count=12,
        )
    return ProfileRow(
        submission_id=uuid.uuid4(),
        user_id=user_id or STUDENT,
        graph_id=uuid.uuid4(),
        graph_type=graph_type,
        input_method=input_method,
        assessment_version=assessment_version,
        assessed_at=EPOCH + dt.timedelta(minutes=minutes),
        profile=profile_,
        spelling_score=spelling_score,
        grammar_score=grammar_score,
    )


BASE = {
    "SECRET_KEY": "a-perfectly-fine-secret-key-over-32-chars",
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
}


def settings(**overrides) -> Settings:
    return Settings(**{**BASE, **overrides})


# ── Reading a stored profile back ────────────────────────────────────────────


class TestProfileParsing:
    def test_a_complete_metrics_blob_parses(self):
        metrics = {**BASE_MEASURES, "word_count": 210.0, "sentence_count": 11.0}

        parsed = Profile.from_metrics(metrics)

        assert parsed is not None
        assert parsed.word_count == 210
        assert parsed.measures["lexical_diversity"] == pytest.approx(0.72)

    @pytest.mark.parametrize(
        "metrics",
        [
            None,
            {},
            "not a mapping",
            [1, 2, 3],
            # One measure short: a release that added a measure cannot read a
            # blob written before it as though the missing one were zero.
            {k: v for k, v in BASE_MEASURES.items() if k != "subordination_ratio"},
            # Present but not a number.
            {**BASE_MEASURES, "word_count": "many", "sentence_count": 11.0},
            # Present but not finite.
            {**BASE_MEASURES, "word_count": float("nan"), "sentence_count": 11.0},
            {**BASE_MEASURES, "word_count": float("inf"), "sentence_count": 11.0},
            # A bool is an int, and an int is a number. It is still corrupt.
            {**BASE_MEASURES, "word_count": True, "sentence_count": 11.0},
        ],
    )
    def test_a_malformed_stored_profile_is_inert(self, metrics):
        """Never an exception. A teacher's page survives one bad row.

        This is the same rule a malformed achievement rule follows: a typo in
        stored data must not cost the person looking at it their screen.
        """
        assert Profile.from_metrics(metrics) is None

    def test_a_row_without_a_profile_reports_no_value_not_zero(self):
        empty = row(profile_=None)

        for measure in MEASURES:
            assert empty.value(measure) is None

    def test_a_column_measure_is_read_from_the_column(self):
        assert row(spelling_score=91.5).value("spelling_score") == pytest.approx(91.5)

    def test_an_unconfigured_engine_reports_none_rather_than_zero(self):
        """A deployment with no grammar checker has no grammar figure.

        Zero would say the student made every possible grammatical error, and
        would sort them below one who genuinely struggled.
        """
        assert row(grammar_score=None).value("grammar_score") is None


# ── Gates ────────────────────────────────────────────────────────────────────


class TestGates:
    def test_two_like_submissions_are_comparable(self):
        assert comparable(row(minutes=10), row(), min_words=120) is None

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            ({"profile_": None}, "no_profile"),
            ({"assessment_version": "1.0.0+different"}, "different_assessment_version"),
            ({"input_method": "handwriting"}, "different_input_method"),
            ({"graph_type": "pie"}, "different_graph_type"),
        ],
    )
    def test_each_gate_excludes_and_says_why(self, kwargs, expected):
        exclusion = comparable(row(minutes=10, **kwargs), row(), min_words=120)

        assert exclusion is not None
        assert exclusion.reason == expected
        assert exclusion.detail

    def test_the_word_floor_excludes_from_either_side(self):
        short = row(minutes=10, word_count=40)

        assert comparable(short, row(), min_words=120).reason == "below_word_floor"
        assert comparable(row(minutes=10), row(word_count=40), min_words=120).reason == (
            "below_word_floor"
        )

    def test_every_reason_slug_is_reachable(self):
        """A slug nothing can produce is a legend entry for an empty bar."""
        produced = {
            comparable(row(minutes=10, profile_=None), row(), min_words=120).reason,
            comparable(row(minutes=10, assessment_version="1.0.0+x"), row(), min_words=120).reason,
            comparable(row(minutes=10, input_method="handwriting"), row(), min_words=120).reason,
            comparable(row(minutes=10, graph_type="bar"), row(), min_words=120).reason,
            comparable(row(minutes=10), row(), min_words=10_000).reason,
        }

        assert produced == set(REASONS)

    def test_no_gate_wording_reads_as_a_verdict(self):
        """The strings a teacher sees describe the pair, never the student."""
        forbidden = ("ai", "cheat", "plagiar", "risk", "suspicio", "misconduct")

        for kwargs in (
            {"profile_": None},
            {"assessment_version": "1.0.0+x"},
            {"input_method": "handwriting"},
            {"graph_type": "pie"},
        ):
            detail = comparable(row(minutes=10, **kwargs), row(), min_words=120).detail
            assert not any(word in detail.lower() for word in forbidden)

    def test_partition_counts_what_it_excluded(self):
        current = row(minutes=100)
        priors = [
            row(minutes=1),
            row(minutes=2),
            row(minutes=3, graph_type="pie"),
            row(minutes=4, input_method="handwriting"),
            row(minutes=5, profile_=None),
        ]

        kept, excluded = partition(current, priors, min_words=120)

        assert len(kept) == 2
        assert excluded == {
            "different_graph_type": 1,
            "different_input_method": 1,
            "no_profile": 1,
        }


class TestSegments:
    def test_a_series_breaks_where_the_version_changes(self):
        rows = [
            row(minutes=1, assessment_version="1.0.0+aaa"),
            row(minutes=2, assessment_version="1.0.0+aaa"),
            row(minutes=3, assessment_version="1.0.0+bbb"),
            row(minutes=4, assessment_version="1.0.0+bbb"),
            row(minutes=5, assessment_version="1.0.0+aaa"),
        ]

        result = segments(rows)

        assert [version for version, _ in result] == ["1.0.0+aaa", "1.0.0+bbb", "1.0.0+aaa"]
        assert [len(chunk) for _, chunk in result] == [2, 2, 1]

    def test_an_empty_series_has_no_segments(self):
        assert segments([]) == []


# ── Baselines ────────────────────────────────────────────────────────────────


class TestBaseline:
    def test_a_first_submission_has_no_baseline(self):
        """``None``, never ``0`` and never "consistent".

        The majority state for most of a term. A zero here would be read as a
        measurement, and "consistent" would be read as a finding — the two
        worst available answers to "we do not know yet".
        """
        assert baseline([], "lexical_diversity", min_baseline=3) is None

    def test_too_few_prior_submissions_is_no_baseline(self):
        rows = [row(minutes=1), row(minutes=2)]

        assert baseline(rows, "lexical_diversity", min_baseline=3) is None

    def test_a_baseline_reports_its_own_sample_size_and_spread(self):
        rows = [
            row(minutes=1, lexical_diversity=0.60),
            row(minutes=2, lexical_diversity=0.70),
            row(minutes=3, lexical_diversity=0.80),
        ]

        base = baseline(rows, "lexical_diversity", min_baseline=3)

        assert base is not None
        assert base.n == 3
        assert base.mean == pytest.approx(0.70)
        assert base.lowest == pytest.approx(0.60)
        assert base.highest == pytest.approx(0.80)
        assert base.spread > 0

    def test_rows_without_the_measure_are_absent_rather_than_zero(self):
        """The grammar case: an unconfigured engine leaves gaps, not noughts."""
        rows = [
            row(minutes=1, grammar_score=90.0),
            row(minutes=2, grammar_score=None),
            row(minutes=3, grammar_score=80.0),
            row(minutes=4, grammar_score=None),
        ]

        base = baseline(rows, "grammar_score", min_baseline=2)

        assert base is not None
        assert base.n == 2
        assert base.mean == pytest.approx(85.0)

    def test_the_floor_applies_per_measure(self):
        """A settled lexical baseline and no grammar baseline is a real state.

        On a server without a grammar engine, refusing the whole comparison
        because one measure is missing would throw away the measures that are
        there.
        """
        rows = [row(minutes=i, grammar_score=None) for i in range(1, 5)]

        assert baseline(rows, "lexical_diversity", min_baseline=3) is not None
        assert baseline(rows, "grammar_score", min_baseline=3) is None


# ── The student comparison ───────────────────────────────────────────────────


class TestCompareStudent:
    def test_a_comparison_reports_the_model_version(self):
        """Nothing is stored, so the version has to travel with the answer."""
        result = compare_student(row(minutes=99), [], min_words=120, min_baseline=3)

        assert result.model_version == CONSISTENCY_MODEL_VERSION

    def test_every_compared_measure_is_present_even_with_no_baseline(self):
        result = compare_student(row(minutes=99), [], min_words=120, min_baseline=3)

        assert tuple(c.measure for c in result.changes) == COMPARED_MEASURES
        assert all(c.baseline is None for c in result.changes)
        assert all(c.difference is None for c in result.changes)
        assert result.has_baseline is False

    def test_a_difference_is_raw_arithmetic_in_the_measure_s_own_units(self):
        priors = [row(minutes=i, mean_sentence_length=14.0) for i in range(1, 4)]
        current = row(minutes=99, mean_sentence_length=26.0)

        result = compare_student(current, priors, min_words=120, min_baseline=3)
        change = next(c for c in result.changes if c.measure == "mean_sentence_length")

        assert change.current == pytest.approx(26.0)
        assert change.baseline is not None
        assert change.difference == pytest.approx(12.0)

    def test_later_submissions_are_never_part_of_a_baseline(self):
        """An old submission's view must not change when the student writes again.

        A baseline is what came before. Including later work would mean a
        teacher looking at attempt two in April saw different numbers from the
        ones they saw in March.
        """
        current = row(minutes=10, lexical_diversity=0.50)
        later = [row(minutes=m, lexical_diversity=0.90) for m in (20, 30, 40)]

        result = compare_student(current, later, min_words=120, min_baseline=3)

        assert result.considered_count == 0
        assert result.compared_count == 0
        assert all(c.baseline is None for c in result.changes)

    def test_a_comparison_never_crosses_an_assessment_version_boundary(self):
        """The series breaks at the boundary; it is never bridged.

        Across a change to the fingerprint the measures are not the same
        quantities, so a baseline drawn through both would be a baseline over
        two different things wearing one name.
        """
        old_engine = [
            row(minutes=i, assessment_version="1.0.0+old", lexical_diversity=0.40)
            for i in range(1, 5)
        ]
        current = row(minutes=99, assessment_version="1.0.0+new")

        result = compare_student(current, old_engine, min_words=120, min_baseline=3)

        assert result.considered_count == 4
        assert result.compared_count == 0
        assert result.excluded == {"different_assessment_version": 4}
        assert all(c.baseline is None for c in result.changes)

    def test_the_excluded_count_is_reported_beside_the_comparison(self):
        """ "Built from 2 of 9" is the difference between weighable and not."""
        priors = [row(minutes=1), row(minutes=2)] + [
            row(minutes=i, graph_type="pie") for i in range(3, 10)
        ]

        result = compare_student(row(minutes=99), priors, min_words=120, min_baseline=2)

        assert result.considered_count == 9
        assert result.compared_count == 2
        assert result.excluded["different_graph_type"] == 7

    def test_no_measure_is_combined_with_another(self):
        """There is no composite, and nothing that could become one.

        A single figure across dimensions is orderable and its components
        cannot be recovered from it, which is what a risk score is.
        """
        result = compare_student(row(minutes=99), [], min_words=120, min_baseline=3)

        assert not hasattr(result, "score")
        assert not hasattr(result, "overall")
        measures = {c.measure for c in result.changes}
        assert measures == set(COMPARED_MEASURES)


# ── The class view ───────────────────────────────────────────────────────────


class TestClassDistribution:
    def test_a_class_view_is_suppressed_below_the_minimum_sample(self):
        """Two failures compound at the same sizes.

        A three-student "distribution" is both statistically meaningless and
        re-identifying, so it is not shown at all rather than shown with a
        caveat.
        """
        rows = [row(user_id=uuid.uuid4(), minutes=i) for i in range(3)]

        assert class_distribution(rows, "lexical_diversity", min_samples=5) is None

    def test_the_minimum_counts_students_not_submissions(self):
        """One prolific student is not a class."""
        one_student = uuid.uuid4()
        rows = [row(user_id=one_student, minutes=i) for i in range(20)]

        assert class_distribution(rows, "lexical_diversity", min_samples=5) is None

    def test_a_distribution_reports_a_spread_and_both_counts(self):
        rows = [
            row(user_id=uuid.uuid4(), minutes=i, lexical_diversity=value)
            for i, value in enumerate([0.50, 0.60, 0.70, 0.80, 0.90])
        ]

        spread = class_distribution(rows, "lexical_diversity", min_samples=5)

        assert spread is not None
        assert spread.students == 5
        assert spread.submissions == 5
        assert spread.median == pytest.approx(0.70)
        assert spread.q1 <= spread.median <= spread.q3

    def test_rows_without_the_measure_do_not_count_toward_the_minimum(self):
        rows = [row(user_id=uuid.uuid4(), minutes=i, grammar_score=None) for i in range(10)]

        assert class_distribution(rows, "grammar_score", min_samples=5) is None

    def test_no_public_function_orders_students_by_any_measure(self):
        """The structural form of "a ranking is an accusation with the wording removed".

        A distribution has no per-student breakdown to sort, and nothing in the
        package's public surface returns students in measure order.
        """
        import dataclasses

        from app.assessment.consistency import Distribution

        fields = {f.name for f in dataclasses.fields(Distribution)}

        assert "students" in fields
        # A collection of students on this object would be something to sort.
        assert not any(
            f.name in {"by_student", "ranked", "outliers", "students_by_measure"}
            for f in dataclasses.fields(Distribution)
        )
        rows = [
            row(user_id=uuid.uuid4(), minutes=i, lexical_diversity=v)
            for i, v in enumerate([0.9, 0.1, 0.5, 0.7, 0.3])
        ]
        spread = class_distribution(rows, "lexical_diversity", min_samples=5)
        assert isinstance(spread.students, int)


# ── Self-overlap ─────────────────────────────────────────────────────────────


class TestSelfOverlap:
    ATTEMPT = (
        "The chart shows the number of visitors to three attractions between "
        "2019 and 2024. Overall, visitor numbers increased at the museum."
    )

    def test_an_unchanged_resubmission_retains_everything(self):
        result = self_overlap(self.ATTEMPT, self.ATTEMPT)

        assert result is not None
        assert result.retained_percentage == pytest.approx(100.0)

    def test_a_rewrite_retains_little(self):
        rewrite = (
            "Between 2019 and 2024 three attractions were compared. Museum "
            "attendance climbed steadily throughout that period."
        )

        result = self_overlap(rewrite, self.ATTEMPT)

        assert result is not None
        assert result.retained_percentage < 20.0

    def test_a_revision_retains_some(self):
        revised = self.ATTEMPT + " Numbers at the castle fluctuated throughout."

        result = self_overlap(revised, self.ATTEMPT)

        assert result is not None
        assert 50.0 < result.retained_percentage < 100.0

    def test_punctuation_and_case_do_not_count_as_a_rewrite(self):
        """A student who repunctuated a sentence still kept the sentence."""
        repunctuated = self.ATTEMPT.upper().replace(",", "").replace(".", " —")

        result = self_overlap(repunctuated, self.ATTEMPT)

        assert result is not None
        assert result.retained_percentage == pytest.approx(100.0)

    @pytest.mark.parametrize(
        ("current", "previous"),
        [("too short", ATTEMPT), (ATTEMPT, "too short"), ("", ""), ("one two three four", ATTEMPT)],
    )
    def test_too_short_to_compare_is_none_not_zero(self, current, previous):
        """Zero would read as "completely rewritten" rather than "cannot tell"."""
        assert self_overlap(current, previous) is None

    def test_containment_is_measured_against_the_new_attempt(self):
        """An attempt that keeps everything and adds more has still kept everything."""
        longer = self.ATTEMPT + " " + self.ATTEMPT.replace("museum", "gallery")

        of_new = self_overlap(longer, self.ATTEMPT)
        of_old = self_overlap(self.ATTEMPT, longer)

        assert of_new is not None and of_old is not None
        assert of_old.retained_percentage > of_new.retained_percentage


# ── The switch ───────────────────────────────────────────────────────────────


class TestTheSwitch:
    def test_the_comparison_layer_refuses_when_disabled(self):
        """Not a silent empty result.

        An empty comparison and a switched-off one look identical to a caller,
        and only one of them is a fact about the student.
        """
        with pytest.raises(ConsistencyDisabledError):
            require_enabled(settings(CONSISTENCY_ANALYTICS_ENABLED=False))

    def test_the_comparison_layer_opens_when_enabled(self):
        assert require_enabled(settings(CONSISTENCY_ANALYTICS_ENABLED=True)) is None


# ── The analyzer itself ──────────────────────────────────────────────────────


@pytest.mark.usefixtures("spacy_model")
class TestTheProfileAnalyzer:
    """Layer 1: what one submission measures, and when it declines to.

    Needs a parsed document, so unlike everything above it runs the real
    pipeline. It still touches no database and reads no history — that is the
    property the whole split exists to preserve.
    """

    LONG = (
        "The chart illustrates electricity generation from three renewable sources "
        "between 2010 and 2024. Overall, solar generation increased dramatically "
        "across the period, whereas hydroelectric output remained broadly stable "
        "throughout. Solar began from a very small base of around five gigawatt "
        "hours and climbed steadily until it overtook hydroelectricity in 2019. "
        "Wind power followed a similar but gentler trajectory, rising from fifteen "
        "to about ninety gigawatt hours over the same years. Hydroelectric output "
        "bottomed out in 2016 before a modest increase towards the end. The most "
        "striking feature is the point at which solar overtook hydroelectricity, "
        "while wind remained the smallest contributor throughout the whole of the "
        "period that is shown in this particular figure."
    )

    def analyzer(self, **overrides):
        from app.assessment.analyzers.writing_profile import WritingProfileAnalyzer

        return WritingProfileAnalyzer(settings(**overrides))

    def test_a_long_answer_is_profiled(self, assessment_context, term_factory):
        ctx = assessment_context(self.LONG, targets=[term_factory("increase")])

        output = self.analyzer(CONSISTENCY_MIN_WORDS=50).run(ctx)

        assert output.status.value == "ok"
        assert set(output.metrics) == set(MEASURES) | {"word_count", "sentence_count"}
        assert output.metrics["word_count"] > 50

    def test_a_short_answer_is_skipped_rather_than_measured_badly(self, assessment_context):
        """Not `FAILED`, and not `OK` with zeroes.

        A short answer is a fact about the answer. Measuring it anyway would
        put a noisy point into a baseline, and a noisy point is worse than a
        missing one because a missing one is visible as missing.
        """
        ctx = assessment_context("The graph goes up and then it goes down again.")

        output = self.analyzer(CONSISTENCY_MIN_WORDS=120).run(ctx)

        assert output.status.value == "skipped"
        assert output.metrics == {}
        assert output.score is None
        assert output.detail is not None

    def test_it_produces_no_issues_and_no_score_on_any_answer(self, assessment_context):
        for text in (self.LONG, "The graph goes up."):
            output = self.analyzer(CONSISTENCY_MIN_WORDS=5).run(assessment_context(text))
            assert output.issues == ()
            assert output.score is None

    def test_the_same_answer_measures_the_same_way_twice(self, assessment_context):
        ctx = assessment_context(self.LONG)
        analyzer = self.analyzer(CONSISTENCY_MIN_WORDS=50)

        assert dict(analyzer.run(ctx).metrics) == dict(analyzer.run(ctx).metrics)

    def test_sentence_variation_separates_even_prose_from_uneven(self, assessment_context):
        even = "Sales rose by ten percent. Costs fell by ten percent. Profit climbed steadily. " * 4
        uneven = (
            "Sales rose. " + "Costs fell steadily across the whole of the period covered by "
            "this figure before recovering towards the very end of it. "
        ) * 4

        analyzer = self.analyzer(CONSISTENCY_MIN_WORDS=5)
        flat = analyzer.run(assessment_context(even)).metrics["sentence_length_variation"]
        varied = analyzer.run(assessment_context(uneven)).metrics["sentence_length_variation"]

        assert varied > flat

    def test_a_single_sentence_has_no_spread_rather_than_an_undefined_one(self, assessment_context):
        one = "Solar generation increased steadily across the whole of the period shown here."

        output = self.analyzer(CONSISTENCY_MIN_WORDS=5).run(assessment_context(one))

        assert output.metrics["sentence_length_variation"] == 0.0

    def test_vocabulary_coverage_follows_the_required_targets(
        self, assessment_context, term_factory
    ):
        targets = [term_factory("increase"), term_factory("fall", category="decrease")]

        used_one = assessment_context(self.LONG, targets=targets)
        coverage = (
            self.analyzer(CONSISTENCY_MIN_WORDS=50).run(used_one).metrics["vocabulary_coverage"]
        )

        assert 0.0 <= coverage <= 100.0

    def test_an_exercise_with_no_required_targets_reports_zero_not_a_crash(
        self, assessment_context
    ):
        ctx = assessment_context(self.LONG, targets=[])

        output = self.analyzer(CONSISTENCY_MIN_WORDS=50).run(ctx)

        assert output.metrics["vocabulary_coverage"] == 0.0

    def test_the_measured_output_parses_back_into_a_profile(self, assessment_context, term_factory):
        """Layer 1 and Layer 2 agree about the shape, asserted rather than assumed.

        The analyzer writes the blob and the profile reads it. Nothing else
        checks that the two agree, and they are in different packages.
        """
        ctx = assessment_context(self.LONG, targets=[term_factory("increase")])

        output = self.analyzer(CONSISTENCY_MIN_WORDS=50).run(ctx)
        parsed = Profile.from_metrics(dict(output.metrics))

        assert parsed is not None
        assert set(parsed.measures) == set(MEASURES)
        assert parsed.word_count > 50

    def test_a_skipped_profile_does_not_parse(self, assessment_context):
        output = self.analyzer(CONSISTENCY_MIN_WORDS=10_000).run(assessment_context(self.LONG))

        assert Profile.from_metrics(dict(output.metrics)) is None

    def test_two_assessments_sharing_an_instant_are_still_ordered(self):
        """``created_at`` defaults to the transaction clock, so ties are real.

        On the timestamp alone neither of a tied pair is earlier than the
        other, so both would drop out of each other's baselines and disappear
        from the history without anything reporting a gap. The submission id
        breaks the tie, which makes "earlier" a total order.
        """
        first = row(minutes=0, lexical_diversity=0.40)
        tied = [row(minutes=0, lexical_diversity=0.40) for _ in range(4)]
        ordered = sorted([first, *tied], key=lambda r: (r.assessed_at, r.submission_id))
        current = ordered[-1]

        result = compare_student(
            current, [r for r in ordered if r is not current], min_words=120, min_baseline=3
        )

        assert result.considered_count == 4
        assert result.compared_count == 4

    def test_the_earliest_of_a_tied_group_has_no_baseline(self):
        """The other half of the same order: someone has to be first."""
        tied = sorted(
            [row(minutes=0) for _ in range(4)], key=lambda r: (r.assessed_at, r.submission_id)
        )

        result = compare_student(tied[0], tied[1:], min_words=120, min_baseline=3)

        assert result.considered_count == 0
        assert all(c.baseline is None for c in result.changes)


class TestReadingTheStoredBlob:
    """The repository's extraction step, which has to survive anything stored.

    ``analyzer_status`` is written by whichever release assessed the
    submission. A row from before this analyzer existed, or from a release
    that shaped the blob differently, is the ordinary case rather than the
    exceptional one.
    """

    @pytest.mark.parametrize(
        "stored",
        [
            None,
            "a string where a blob should be",
            [{"writing_profile": {}}],
            42,
            {},
            {"writing_profile": None},
            {"writing_profile": "not a mapping"},
            {"writing_profile": {}},
            {"grammar": {"metrics": {}}},
        ],
    )
    def test_anything_unreadable_yields_no_profile(self, stored):
        from app.repositories.assessment import _profile_metrics

        assert Profile.from_metrics(_profile_metrics(stored)) is None

    def test_a_well_formed_blob_yields_a_profile(self):
        from app.repositories.assessment import _profile_metrics

        stored = {
            "writing_profile": {
                "status": "ok",
                "metrics": {**BASE_MEASURES, "word_count": 180.0, "sentence_count": 9.0},
            }
        }

        assert Profile.from_metrics(_profile_metrics(stored)) is not None

    def test_has_profile_and_value_agree(self):
        assert row().has_profile is True
        assert row(profile_=None).has_profile is False
