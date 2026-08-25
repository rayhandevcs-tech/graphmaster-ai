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
    # different facts, and a zero cannot tell them apart.
    assert detail.grammar_score is None
    assert "grammar" not in detail.analyzer_status


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
    assert {i.source.split(":")[0] for i in detail.issues} <= {
        "spelling",
        "sentence",
        "word_usage",
        "vocabulary",
        "writing",
    }


async def test_the_analyzer_status_records_what_ran(client, student, seeded_graph, db):
    _, headers = student
    submission_id = await score_answer(client, headers, seeded_graph, FLAWED)

    detail = await stored(db, submission_id)

    assert set(detail.analyzer_status) == {
        "vocabulary",
        "writing",
        "spelling",
        "sentence",
        "word_usage",
    }
    assert all(entry["status"] == "ok" for entry in detail.analyzer_status.values())
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
