"""The assessment written beside a score, against a real database.

The unit tests prove the analyzers find the right things. These prove the
findings survive the trip into PostgreSQL — that the offsets still index the
student's own text after a round trip, that the constraints reject what they
are there to reject, and above all that a submission is still scored when the
diagnostic half of the work goes wrong.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError

from app.models.assessment import AssessmentDetail, AssessmentIssue
from app.models.enums import AssessmentStatus, UserRole
from app.models.submission import Score

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("spacy_model")]

SUBMISSIONS = "/api/v1/submissions"

#: Deliberately imperfect: two misspellings, no overview, one conversational
#: word. Long enough that the length check does not swamp everything else.
FLAWED = (
    "Solar generation rose gradualy from a very small base in 2010 and it "
    "continued to climb across the whole of the period that is shown here. "
    "Hydroelectric output remained stable throughout these years, while wind "
    "power fluctuated a little before increasing towards the end. The gap "
    "between solar and hydroelectric narrowed considerably and was noticable "
    "by the final year of the period covered by this particular figure."
)


@pytest.fixture
async def seeded_graph(db, seeded_vocabulary, user_factory):
    from app.db.seed.runner import seed_graphs
    from app.models.content import Graph

    author = await user_factory(role=UserRole.TEACHER, email="assess-author@test.edu")
    await seed_graphs(db, author_id=author.id)
    return (await db.execute(select(Graph).where(Graph.graph_type == "line").limit(1))).scalar_one()


@pytest.fixture
async def student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="assess@test.edu")
    return user, auth_headers(user)


async def score_answer(client, headers, graph, text: str) -> str:
    opened = await client.post(
        SUBMISSIONS, headers=headers, json={"graph_id": str(graph.id), "input_method": "typed"}
    )
    submission_id = opened.json()["id"]
    await client.patch(f"{SUBMISSIONS}/{submission_id}/text", headers=headers, json={"text": text})
    marked = await client.post(f"{SUBMISSIONS}/{submission_id}/analyze", headers=headers)
    assert marked.status_code == 200, marked.text
    return submission_id


async def stored(db, submission_id: str) -> AssessmentDetail:
    from sqlalchemy.orm import selectinload

    return (
        await db.execute(
            select(AssessmentDetail)
            .where(AssessmentDetail.submission_id == submission_id)
            .options(selectinload(AssessmentDetail.issues))
        )
    ).scalar_one()


# ── The happy path ───────────────────────────────────────────────────────────


async def test_scoring_writes_an_assessment_beside_the_score(client, student, seeded_graph, db):
    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    detail = await stored(db, submission_id)

    assert detail.status == AssessmentStatus.COMPLETE.value
    assert detail.assessment_version.startswith("1.0.0+")
    assert detail.issue_count == len(detail.issues)
    assert detail.issue_count > 0
    # The scores that belong to this table, and only those: vocabulary and
    # writing live on `scores` and are deliberately not copied.
    assert detail.spelling_score is not None
    assert detail.sentence_score is not None
    assert detail.word_usage_score is not None


async def test_an_analyzer_that_did_not_run_stores_null_rather_than_zero(
    client, student, seeded_graph, db
):
    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    detail = await stored(db, submission_id)

    # "Grammar never ran here" and "grammar ran and the writing was poor" are
    # different facts, and a zero cannot tell them apart. On a default
    # deployment the analyzer is configured but has no engine to call, so the
    # row records that it was asked and reports no score — rather than
    # recording a nought that would drag every class average down towards a
    # figure nobody measured.
    assert detail.grammar_score is None
    assert detail.analyzer_status["grammar"]["status"] == "unavailable"
    assert detail.analyzer_status["grammar"]["score"] is None


async def test_the_stored_offsets_still_index_the_student_s_own_text(
    client, student, seeded_graph, db
):
    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    detail = await stored(db, submission_id)
    spans = [i for i in detail.issues if i.original_text]

    assert spans, "expected at least one issue anchored to a span"
    for issue in spans:
        assert FLAWED[issue.start_index : issue.end_index] == issue.original_text


async def test_the_issues_come_back_in_reading_order(client, student, seeded_graph, db):
    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    detail = await stored(db, submission_id)
    starts = [i.start_index for i in detail.issues]

    # A student works through their answer from the top; the relationship's
    # order_by is what makes that true without the caller sorting.
    assert starts == sorted(starts)


async def test_every_issue_records_which_analyzer_found_it(client, student, seeded_graph, db):
    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    detail = await stored(db, submission_id)

    # Without this an audit of a false positive has nowhere to start.
    assert all(i.source for i in detail.issues)
    from app.core.config import get_settings

    assert {i.source.split(":")[0] for i in detail.issues} <= set(
        get_settings().assessment_analyzers
    )


async def test_the_analyzer_status_records_what_ran(client, student, seeded_graph, db):
    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    detail = await stored(db, submission_id)

    # The configured set, whatever it currently is — this asserts that every
    # analyzer that ran is recorded, not which ones a given release ships.
    from app.core.config import get_settings

    assert set(detail.analyzer_status) == set(get_settings().assessment_analyzers)

    # Every analyzer either ran or said why it could not. "Unavailable" is a
    # deployment fact rather than a fault — grammar needs an engine this
    # server does not have — and it is the reason the assessment as a whole is
    # still complete.
    statuses = {name: entry["status"] for name, entry in detail.analyzer_status.items()}
    assert statuses["grammar"] == "unavailable"
    assert all(status == "ok" for name, status in statuses.items() if name != "grammar")
    assert detail.status == AssessmentStatus.COMPLETE.value
    assert set(detail.analyzer_audiences) == set(detail.analyzer_status)


async def test_only_mistakes_are_counted_as_errors(client, student, seeded_graph, db):
    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    detail = await stored(db, submission_id)
    suggestions = [i for i in detail.issues if i.severity == "info"]

    assert suggestions, "expected at least one suggestion in this answer"
    # Telling a student they made nine mistakes when four were preferences is
    # what the severity scale exists to prevent.
    assert detail.error_count == detail.issue_count - len(suggestions)


# ── The guarantee, through the whole stack ───────────────────────────────────


async def test_a_submission_is_still_scored_when_the_assessment_cannot_be_built(
    client, student, seeded_graph, db, monkeypatch
):
    """The end-to-end form of the isolation guarantee.

    The unit test proves ``analyse`` survives it. This proves the *request*
    does: the score is written, the XP is awarded, and the student gets their
    result — with no assessment row, which is the same shape a submission
    scored before this feature existed has.
    """
    from app.assessment import engine

    monkeypatch.setattr(
        engine,
        "build_analyzers",
        lambda _settings: (_ for _ in ()).throw(RuntimeError("registry is corrupt")),
    )

    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    score = (
        await db.execute(select(Score).where(Score.submission_id == submission_id))
    ).scalar_one()
    assessment = (
        await db.execute(
            select(AssessmentDetail).where(AssessmentDetail.submission_id == submission_id)
        )
    ).scalar_one_or_none()

    assert score.final_score >= 0
    assert assessment is None


async def test_disabling_assessment_leaves_the_pipeline_working(
    client, student, seeded_graph, db, monkeypatch
):
    from app.core.config import get_settings

    # Patched where the analysis service reads it, not where the engine falls
    # back to it: `analyse` passes its settings down explicitly, so the
    # engine's own `get_settings()` never runs on this path.
    monkeypatch.setattr(
        "app.services.analysis.get_settings",
        lambda: get_settings().model_copy(update={"ASSESSMENT_ENABLED": False}),
    )

    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    assert (
        await db.execute(
            select(AssessmentDetail).where(AssessmentDetail.submission_id == submission_id)
        )
    ).scalar_one_or_none() is None


async def test_deleting_a_submission_takes_its_assessment_with_it(
    client, student, seeded_graph, db
):
    from app.models.submission import Submission

    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    submission = await db.get(Submission, submission_id)
    await db.delete(submission)
    await db.flush()

    remaining = (
        (
            await db.execute(
                select(AssessmentIssue).join(
                    AssessmentDetail, AssessmentDetail.id == AssessmentIssue.assessment_id
                )
            )
        )
        .scalars()
        .all()
    )

    # Cascade all the way through: an orphaned issue references a span in text
    # that no longer exists.
    assert remaining == []


# ── The constraints ──────────────────────────────────────────────────────────


class TestConstraints:
    async def test_a_second_assessment_for_one_submission_is_refused(
        self, client, student, seeded_graph, db
    ):
        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        db.add(AssessmentDetail(submission_id=submission_id, assessment_version="1.0.0+x"))

        # One assessment per submission, enforced by the database rather than
        # assumed by the service — the same guarantee `scores` has.
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    @pytest.mark.parametrize(
        ("column", "value"),
        [("spelling_score", 101.0), ("sentence_score", -1.0), ("word_usage_score", 250.0)],
    )
    async def test_a_score_outside_the_scale_is_refused(
        self, client, student, seeded_graph, db, column: str, value: float
    ):
        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)
        detail = await stored(db, submission_id)

        setattr(detail, column, value)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    async def test_more_errors_than_issues_is_refused(self, client, student, seeded_graph, db):
        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)
        detail = await stored(db, submission_id)

        # A mistake is an issue, so there cannot be more of the first.
        detail.error_count = detail.issue_count + 1
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    async def test_an_inverted_span_is_refused(self, client, student, seeded_graph, db):
        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)
        detail = await stored(db, submission_id)

        issue = detail.issues[0]
        issue.start_index, issue.end_index = 90, 12
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    async def test_an_unknown_severity_is_refused(self, client, student, seeded_graph, db):
        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)
        detail = await stored(db, submission_id)

        # The CHECK is generated from the Python enum, so this is also what
        # catches the two drifting apart.
        detail.issues[0].severity = "catastrophic"
        with pytest.raises((IntegrityError, StatementError)):
            await db.flush()
        await db.rollback()


# ── The repository's own reads ───────────────────────────────────────────────


class TestRepositoryReads:
    async def test_it_reads_one_submission_s_assessment_with_its_issues(
        self, client, student, seeded_graph, db
    ):
        from app.repositories.assessment import AssessmentRepository

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        found = await AssessmentRepository(db).for_submission(submission_id)

        assert found is not None
        assert found.issues, "the issues must be loaded, not lazily deferred"
        assert [i.start_index for i in found.issues] == sorted(i.start_index for i in found.issues)

    async def test_a_submission_with_no_assessment_reads_as_none(self, db, seeded_graph, student):
        from app.models.enums import InputMethod, SubmissionStatus
        from app.models.submission import Submission
        from app.repositories.assessment import AssessmentRepository

        user, _ = student
        draft = Submission(
            user_id=user.id,
            graph_id=seeded_graph.id,
            input_method=InputMethod.TYPED.value,
            status=SubmissionStatus.DRAFT.value,
        )
        db.add(draft)
        await db.flush()

        assert await AssessmentRepository(db).for_submission(draft.id) is None

    async def test_issue_counts_are_grouped_in_the_database(
        self, client, student, seeded_graph, db
    ):
        from app.repositories.assessment import AssessmentRepository

        _, headers = student
        first = await score_answer(client, headers, seeded_graph, FLAWED)
        second = await score_answer(client, headers, seeded_graph, FLAWED)

        counts = await AssessmentRepository(db).issue_counts([first, second])

        # Every category, including the empty ones: a missing key reads as
        # missing data, a zero reads as a finding.
        from app.models.enums import IssueCategory

        assert set(counts) == {c.value for c in IssueCategory}
        assert counts["spelling"] > 0
        assert counts["grammar"] == 0

    async def test_counting_across_no_submissions_still_names_every_category(self, db):
        from app.models.enums import IssueCategory
        from app.repositories.assessment import AssessmentRepository

        counts = await AssessmentRepository(db).issue_counts([])

        assert counts == {c.value: 0 for c in IssueCategory}


# ── Graph-accuracy claims ────────────────────────────────────────────────────


MISREAD = (
    "Overall, solar output fell steadily across the whole of the period covered by "
    "this graph. The figures reached their peak in 2020 and then declined again "
    "towards the final year. Output was consistently lower at the end than it had "
    "been at the start of the period, and the pattern was clear throughout the "
    "years that the chart covers in this particular figure."
)


class TestGraphAccuracyClaims:
    async def test_claims_are_stored_with_their_verdicts(self, client, student, seeded_graph, db):
        from sqlalchemy.orm import selectinload

        from app.models.assessment import GraphAccuracyClaim

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, MISREAD)

        detail = (
            await db.execute(
                select(AssessmentDetail)
                .where(AssessmentDetail.submission_id == submission_id)
                .options(selectinload(AssessmentDetail.claims))
            )
        ).scalar_one()

        assert detail.claims, "the seeded line graph supports checkable claims"
        assert {c.verdict for c in detail.claims} <= {"correct", "incorrect", "unverified"}
        assert all(isinstance(c, GraphAccuracyClaim) for c in detail.claims)

    async def test_a_contradicted_claim_is_linked_to_the_correction_it_produced(
        self, client, student, seeded_graph, db
    ):
        from sqlalchemy.orm import selectinload

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, MISREAD)

        detail = (
            await db.execute(
                select(AssessmentDetail)
                .where(AssessmentDetail.submission_id == submission_id)
                .options(
                    selectinload(AssessmentDetail.claims), selectinload(AssessmentDetail.issues)
                )
            )
        ).scalar_one()

        wrong = [c for c in detail.claims if c.verdict == "incorrect"]
        assert wrong, "this answer describes a rising series as falling"
        assert all(c.issue_id is not None for c in wrong)

        linked = {c.issue_id for c in wrong}
        graph_issues = {i.id for i in detail.issues if i.category == "graph_accuracy"}
        assert linked <= graph_issues

    async def test_a_correct_claim_carries_no_correction(self, client, student, seeded_graph, db):
        from sqlalchemy.orm import selectinload

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, MISREAD)

        detail = (
            await db.execute(
                select(AssessmentDetail)
                .where(AssessmentDetail.submission_id == submission_id)
                .options(selectinload(AssessmentDetail.claims))
            )
        ).scalar_one()

        for claim in detail.claims:
            if claim.verdict != "incorrect":
                assert claim.issue_id is None

    async def test_an_unverified_claim_naming_a_series_is_refused(
        self, client, student, seeded_graph, db
    ):
        from app.models.assessment import GraphAccuracyClaim

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, MISREAD)
        detail = await stored(db, submission_id)

        # Enforced in the dataclass, and again here: a claim that resolved to a
        # series is one the engine could judge, and recording it as unverified
        # *and* attributed would make the accuracy figure unreadable.
        db.add(
            GraphAccuracyClaim(
                assessment_id=detail.id,
                claim_type="trend",
                series_label="Solar",
                claimed="fell",
                actual="increase",
                verdict="unverified",
                start_index=0,
                end_index=4,
                issue_id=detail.issues[0].id,
            )
        )
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()

    async def test_the_claims_go_when_the_submission_does(self, client, student, seeded_graph, db):
        from app.models.assessment import GraphAccuracyClaim
        from app.models.submission import Submission

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, MISREAD)

        await db.delete(await db.get(Submission, submission_id))
        await db.flush()

        remaining = (await db.execute(select(GraphAccuracyClaim))).scalars().all()
        assert remaining == []


# ── Grammar ──────────────────────────────────────────────────────────────────


class LoudGrammarProvider:
    """A stand-in engine that objects to every long word.

    A real LanguageTool would need a JVM, a 250MB download and a container in
    CI. What these tests are about is not LanguageTool's accuracy — it is that
    whatever a grammar engine finds lands in the right table, indexes the
    student's own text, and changes nothing about what they were awarded.
    """

    name = "loud"

    def is_available(self) -> bool:
        return True

    def check(self, text: str, *, language: str):
        from app.assessment.grammar.base import GrammarMatch, GrammarReport
        from app.models.enums import IssueSeverity

        matches, offset = [], 0
        for word in text.split(" "):
            if len(word) > 6:
                matches.append(
                    GrammarMatch(
                        subtype="subject_verb_agreement",
                        severity=IssueSeverity.MEDIUM,
                        original_text=word,
                        explanation="That does not agree with its subject.",
                        start=offset,
                        end=offset + len(word),
                        suggested_text=word.rstrip(".,") + "s",
                        confidence=0.85,
                        rule_id="TEST_AGREEMENT",
                    )
                )
            offset += len(word) + 1
        return GrammarReport(
            matches=tuple(matches), provider=self.name, latency_ms=7.5, checked_chars=len(text)
        )


@pytest.fixture
def loud_grammar(monkeypatch):
    """Point the registry's grammar builder at the stand-in engine."""
    from app.assessment import registry
    from app.assessment.analyzers.grammar import GrammarAnalyzer

    builders = dict(registry.BUILDERS)
    builders["grammar"] = lambda settings: GrammarAnalyzer(settings, provider=LoudGrammarProvider())
    monkeypatch.setattr(registry, "BUILDERS", builders)


class TestGrammarPersistence:
    async def test_grammar_findings_land_in_the_shared_issue_table(
        self, client, student, seeded_graph, db, loud_grammar
    ):
        from app.models.enums import IssueCategory

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        detail = await stored(db, submission_id)
        grammar = [i for i in detail.issues if i.category == IssueCategory.GRAMMAR.value]

        # One table, not a parallel one: the result page shows a single list in
        # reading order, and "the mistakes this class makes most" is one query.
        assert grammar
        assert all(i.subtype == "subject_verb_agreement" for i in grammar)
        assert all(i.source.endswith("TEST_AGREEMENT") for i in grammar)

    async def test_the_stored_grammar_offsets_index_the_students_own_text(
        self, client, student, seeded_graph, db, loud_grammar
    ):
        from app.models.enums import IssueCategory

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        detail = await stored(db, submission_id)
        for issue in detail.issues:
            if issue.category == IssueCategory.GRAMMAR.value:
                assert FLAWED[issue.start_index : issue.end_index] == issue.original_text

    async def test_the_grammar_score_reaches_its_own_column(
        self, client, student, seeded_graph, db, loud_grammar
    ):
        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        detail = await stored(db, submission_id)

        assert detail.grammar_score is not None
        assert 0.0 <= float(detail.grammar_score) <= 100.0
        assert detail.analyzer_status["grammar"]["status"] == "ok"
        assert detail.analyzer_status["grammar"]["metrics"]["grammar_accuracy_percentage"] < 100.0

    async def test_the_provider_latency_is_recorded_for_an_operator(
        self, client, student, seeded_graph, db, loud_grammar
    ):
        # The number that answers whether a remote engine is worth its round
        # trip, kept apart from the analyzer's own cost.
        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        metrics = (await stored(db, submission_id)).analyzer_status["grammar"]["metrics"]

        assert metrics["provider_latency_ms"] == pytest.approx(7.5)

    async def test_a_grammar_engine_that_fails_marks_the_assessment_partial_not_the_score(
        self, client, student, seeded_graph, db, monkeypatch
    ):
        """Feature 5, through the whole stack.

        A configured engine that does not answer is a fault worth someone's
        attention. It is not worth the student's submission, which has already
        been scored by the time the diagnostic pass runs.
        """
        from app.assessment import registry
        from app.assessment.analyzers.grammar import GrammarAnalyzer
        from app.assessment.grammar.base import GrammarCheckError

        class Broken:
            name = "broken"

            def is_available(self) -> bool:
                return True

            def check(self, text: str, *, language: str):
                raise GrammarCheckError("The grammar service could not be reached (TimeoutError).")

        builders = dict(registry.BUILDERS)
        builders["grammar"] = lambda settings: GrammarAnalyzer(settings, provider=Broken())
        monkeypatch.setattr(registry, "BUILDERS", builders)

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        detail = await stored(db, submission_id)
        score = (
            await db.execute(select(Score).where(Score.submission_id == submission_id))
        ).scalar_one()

        assert detail.status == AssessmentStatus.PARTIAL.value
        assert detail.analyzer_status["grammar"]["status"] == "failed"
        assert detail.grammar_score is None
        assert score.final_score is not None  # the student was still marked

    async def test_the_failure_detail_names_no_endpoint(
        self, client, student, seeded_graph, db, monkeypatch
    ):
        """This string is stored on a row a teacher's report will read."""
        from app.assessment import registry
        from app.assessment.analyzers.grammar import GrammarAnalyzer
        from app.assessment.grammar.providers import LocalLanguageToolProvider

        def dead(url, body, timeout):
            if url.endswith("/v2/languages"):
                return 200, b"[]"
            raise TimeoutError("timed out")

        def build(settings):
            configured = settings.model_copy(
                update={"GRAMMAR_HOST": "lt-internal.example", "GRAMMAR_API_URL": None}
            )
            provider = LocalLanguageToolProvider(configured, transport=dead)
            provider._healthy, provider._checked_at = True, float("inf")
            return GrammarAnalyzer(configured, provider=provider)

        builders = dict(registry.BUILDERS)
        builders["grammar"] = build
        monkeypatch.setattr(registry, "BUILDERS", builders)

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        detail = await stored(db, submission_id)

        assert "lt-internal" not in (detail.analyzer_status["grammar"]["detail"] or "")


class TestGrammarChangesNothingAwarded:
    """Regression protections 1-4, through the API rather than the engine.

    The unit tests prove the score object is identical. These prove the same
    of everything downstream of it: the row that is stored, the XP ledger, and
    the figure a leaderboard is built from.
    """

    async def test_the_same_answer_earns_the_same_score_and_xp_with_grammar_running(
        self, client, seeded_graph, db, user_factory, auth_headers, monkeypatch
    ):
        from sqlalchemy import func

        from app.models.enums import UserRole
        from app.models.gamification import XPEvent

        async def score_as(email: str) -> tuple[Score, int, int]:
            user = await user_factory(role=UserRole.STUDENT, email=email)
            submission_id = await score_answer(client, auth_headers(user), seeded_graph, FLAWED)
            score = (
                await db.execute(select(Score).where(Score.submission_id == submission_id))
            ).scalar_one()
            awarded = (
                await db.execute(
                    select(func.coalesce(func.sum(XPEvent.amount), 0)).where(
                        XPEvent.user_id == user.id
                    )
                )
            ).scalar_one()
            await db.refresh(user)
            return score, int(awarded), user.total_xp

        without = await score_as("grammar-off@test.edu")

        from app.assessment import registry
        from app.assessment.analyzers.grammar import GrammarAnalyzer

        builders = dict(registry.BUILDERS)
        builders["grammar"] = lambda s: GrammarAnalyzer(s, provider=LoudGrammarProvider())
        monkeypatch.setattr(registry, "BUILDERS", builders)

        with_grammar = await score_as("grammar-on@test.edu")

        assert with_grammar[0].final_score == without[0].final_score
        assert with_grammar[0].vocabulary_score == without[0].vocabulary_score
        assert with_grammar[0].writing_score == without[0].writing_score
        assert with_grammar[0].vocabulary_percentage == without[0].vocabulary_percentage
        # The tier drives the badge and the animation the student is shown.
        assert with_grammar[0].reward_tier == without[0].reward_tier
        # XP follows the score, and the leaderboard follows XP.
        assert with_grammar[1] == without[1]
        assert with_grammar[2] == without[2]
        # …and the engine version did not move, so the two remain comparable.
        assert with_grammar[0].engine_version == without[0].engine_version


class TestGrammarAnalytics:
    """The aggregation a class report is built from.

    Foundation rather than presentation: no endpoint exposes these yet, and
    they are teacher-facing by construction — every one takes a set of
    submission ids the caller has already established the teacher may see.
    """

    async def test_the_commonest_mistakes_are_counted_in_the_database(
        self, client, student, seeded_graph, db, loud_grammar
    ):
        from app.models.enums import IssueCategory
        from app.repositories.assessment import AssessmentRepository

        _, headers = student
        first = await score_answer(client, headers, seeded_graph, FLAWED)
        second = await score_answer(client, headers, seeded_graph, FLAWED)

        frequency = await AssessmentRepository(db).issue_frequency(
            [first, second], category=IssueCategory.GRAMMAR
        )

        assert frequency
        assert frequency[0][0] == "subject_verb_agreement"
        assert frequency[0][1] >= 2
        # Most frequent first, and only grammar: a class report asking about
        # grammar must not be answered with the spelling mistakes as well.
        assert [count for _, count in frequency] == sorted(
            (count for _, count in frequency), reverse=True
        )

    async def test_the_frequency_of_every_category_is_available_too(
        self, client, student, seeded_graph, db, loud_grammar
    ):
        from app.repositories.assessment import AssessmentRepository

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        everything = await AssessmentRepository(db).issue_frequency([submission_id])

        assert len({subtype for subtype, _ in everything}) > 1

    async def test_a_summary_reports_how_many_submissions_were_actually_assessed(
        self, client, student, seeded_graph, db, loud_grammar
    ):
        from app.repositories.assessment import AssessmentRepository

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        summary = await AssessmentRepository(db).score_summary([submission_id], "grammar")

        assert summary.assessed_count == 1
        assert summary.average is not None

    async def test_an_unassessed_cohort_reports_none_rather_than_zero(
        self, client, student, seeded_graph, db
    ):
        """The rule that keeps a trend line honest.

        No grammar engine is configured here, so no submission carries a
        grammar score. A class whose grammar was never checked is not a class
        that scored nothing, and a zero would sort them below one that
        genuinely struggled — and would draw a line through a gap in the data.
        """
        from app.repositories.assessment import AssessmentRepository

        _, headers = student
        submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

        summary = await AssessmentRepository(db).score_summary([submission_id], "grammar")

        assert summary.assessed_count == 0
        assert summary.average is None

    async def test_a_summary_over_no_submissions_is_unavailable_not_zero(self, db):
        from app.repositories.assessment import AssessmentRepository

        summary = await AssessmentRepository(db).score_summary([], "grammar")

        assert (summary.assessed_count, summary.average) == (0, None)
        assert await AssessmentRepository(db).issue_frequency([]) == []
        assert await AssessmentRepository(db).score_series([], "grammar") == []

    async def test_the_trend_series_carries_only_assessed_submissions(
        self, client, student, seeded_graph, db, loud_grammar
    ):
        """Returned unbucketed on purpose.

        A trend line's periods are boundaries in ``PLATFORM_TIMEZONE`` — a
        cohort must roll over together — and expressing that in SQL would push
        a timezone conversion into the database, where SQLite and PostgreSQL
        disagree about how to do it. A period with nothing in it comes out
        empty, which is what a broken line is drawn from.
        """
        from app.repositories.assessment import AssessmentRepository

        _, headers = student
        first = await score_answer(client, headers, seeded_graph, FLAWED)
        second = await score_answer(client, headers, seeded_graph, FLAWED)

        series = await AssessmentRepository(db).score_series([first, second], "grammar")

        assert len(series) == 2
        assert [when for when, _ in series] == sorted(when for when, _ in series)
        assert all(0.0 <= score <= 100.0 for _, score in series)

    async def test_asking_for_an_analyzer_with_no_column_is_a_clear_failure(self, db):
        """An empty report and a programming error must not look the same.

        Answering "no data" for a misspelled analyzer name would report a
        working class as one with nothing to show — the same lie an empty
        forbidden report tells.
        """
        from app.repositories.assessment import AssessmentRepository

        with pytest.raises(ValueError, match="vocabulary"):
            await AssessmentRepository(db).score_summary([], "vocabulary")
