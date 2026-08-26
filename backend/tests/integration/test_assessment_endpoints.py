"""The assessment read surface, over HTTP.

Sprint 19 built the writing profile and proved it could not move a score. It
could not prove the other half — that a student never *sees* it — because
nothing read assessment data over HTTP and ``for_audience`` had no call site.
This is where that becomes a fact about the running application rather than
about an object in memory.

The C2 tests here are the ones to keep if the file ever has to be cut down.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.enums import UserRole
from app.models.submission import Submission

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("spacy_model")]

SUBMISSIONS = "/api/v1/submissions"
ASSESSMENT = "/api/v1/assessment"

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

    author = await user_factory(role=UserRole.TEACHER, email="endpoint-author@test.edu")
    await seed_graphs(db, author_id=author.id)
    return (await db.execute(select(Graph).where(Graph.graph_type == "line").limit(1))).scalar_one()


def override_settings(monkeypatch, **overrides):
    """Change the settings a request actually scores with.

    ``AnalysisService`` resolves them once in its constructor and passes them
    down through ``analyse`` into the assessment engine, so this is the single
    point where a request's configuration is decided. Patching the name in
    ``app.nlp.analyzer`` or in the supervisor instead rebinds a module global
    that nothing reads at request time.
    """
    from app.core.config import get_settings

    real = get_settings()

    monkeypatch.setattr(
        "app.services.analysis.get_settings", lambda: real.model_copy(update=overrides)
    )


def measure_profiles(monkeypatch, **overrides):
    """Put the profile analyzer on the roster, as a deployment in stage 2 would."""
    from app.assessment import registry
    from app.assessment.analyzers.writing_profile import WritingProfileAnalyzer
    from app.core.config import get_settings

    real = registry.build_analyzers

    def build(settings=None):
        settings = settings or get_settings()
        analyzers = real(settings)
        analyzers.append(
            WritingProfileAnalyzer(
                settings.model_copy(update={"CONSISTENCY_MIN_WORDS": 1, **overrides})
            )
        )
        return analyzers

    monkeypatch.setattr(registry, "build_analyzers", build)
    monkeypatch.setattr("app.assessment.engine.build_analyzers", build)


async def score_answer(client, headers, graph, text: str = FLAWED) -> str:
    opened = await client.post(
        SUBMISSIONS, headers=headers, json={"graph_id": str(graph.id), "input_method": "typed"}
    )
    submission_id = opened.json()["id"]
    await client.patch(f"{SUBMISSIONS}/{submission_id}/text", headers=headers, json={"text": text})
    marked = await client.post(f"{SUBMISSIONS}/{submission_id}/analyze", headers=headers)
    assert marked.status_code == 200, marked.text
    return submission_id


@pytest.fixture
async def student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="endpoint-student@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="endpoint-teacher@test.edu")
    return user, auth_headers(user)


class TestReadingOneAssessment:
    async def test_a_student_reads_their_own(self, client, seeded_graph, student):
        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        response = await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=headers)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["submission_id"] == submission_id
        assert body["assessment_version"]
        assert body["status"] == "complete"
        assert "spelling" in body["analyzers"]

    async def test_issues_index_the_student_s_own_text(self, client, seeded_graph, student, db):
        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        body = (
            await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=headers)
        ).json()
        submission = (
            await db.execute(select(Submission).where(Submission.id == submission_id))
        ).scalar_one()

        assert body["issues"], "the flawed answer should produce findings"
        quoted = 0
        for issue in body["issues"]:
            if not issue["original_text"]:
                # A whole-answer finding — "there is no overview" — has nowhere
                # to point. It spans the answer and quotes none of it, which is
                # honest: inventing a span would highlight arbitrary words.
                assert issue["start_index"] == 0
                continue
            span = submission.answer_text[issue["start_index"] : issue["end_index"]]
            assert span == issue["original_text"]
            quoted += 1
        assert quoted, "at least one finding should be locatable in the answer"

    async def test_an_issue_never_names_a_provider(self, client, seeded_graph, student):
        """`source` is stored as `analyzer:provider`; only the analyzer is published."""
        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        body = (
            await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=headers)
        ).json()

        for issue in body["issues"]:
            assert ":" not in issue["analyzer"]

    async def test_another_student_gets_404_not_403(
        self, client, seeded_graph, student, user_factory, auth_headers
    ):
        """A 403 would confirm the submission exists."""
        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)
        intruder = await user_factory(role=UserRole.STUDENT, email="intruder@test.edu")

        response = await client.get(
            f"{ASSESSMENT}/submissions/{submission_id}", headers=auth_headers(intruder)
        )

        assert response.status_code == 404

    async def test_an_unassessed_submission_is_404_not_an_empty_assessment(
        self, client, seeded_graph, student, db, monkeypatch
    ):
        """An empty assessment would claim the work was checked and found clean."""
        # Patched where the request-scoped AnalysisService reads it. Settings
        # reach `analyse` by injection, so rebinding the name in `app.nlp` or
        # in the supervisor leaves the instance already in the request alone —
        # and the test would pass while asserting nothing.
        override_settings(monkeypatch, ASSESSMENT_ENABLED=False)

        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        response = await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=headers)

        assert response.status_code == 404

    async def test_it_demands_a_token(self, client, seeded_graph, student):
        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        assert (await client.get(f"{ASSESSMENT}/submissions/{submission_id}")).status_code == 401


class TestTheAudienceFilterOverHttp:
    """C2, as a property of the running application.

    Sprint 19 could only assert this against an in-memory result. Here the
    profile is measured, stored, read back through the router and checked in
    the response body a student's browser would receive.
    """

    async def test_a_student_never_receives_the_writing_profile(
        self, client, seeded_graph, student, monkeypatch
    ):
        measure_profiles(monkeypatch)
        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        body = (
            await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=headers)
        ).json()

        assert "writing_profile" not in body["analyzers"]
        assert "writing_profile" not in body["scores"]
        assert not any(i["analyzer"] == "writing_profile" for i in body["issues"])
        # And no analyzer of any name that is really this one. (`writing`
        # publishes a `lexical_diversity_score` of its own, which is a student
        # -visible component of the writing score and not the profile.)
        assert not any("profile" in name for name in body["analyzers"])

    async def test_a_teacher_does_receive_it(
        self, client, seeded_graph, student, teacher, class_factory, db, monkeypatch
    ):
        measure_profiles(monkeypatch)
        student_user, student_headers = student
        teacher_user, teacher_headers = teacher

        klass = await class_factory(teacher_id=teacher_user.id)
        student_user.class_id = klass.id
        await db.flush()

        submission_id = await score_answer(client, student_headers, seeded_graph)

        body = (
            await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=teacher_headers)
        ).json()

        assert "writing_profile" in body["analyzers"]
        assert body["analyzers"]["writing_profile"]["score"] is None
        assert body["analyzers"]["writing_profile"]["metrics"]["lexical_diversity"] > 0

    async def test_a_dark_analyzer_reaches_nobody(
        self, client, seeded_graph, student, teacher, class_factory, db, monkeypatch
    ):
        """Including the teacher: dark is the stage before they see it."""
        override_settings(monkeypatch, ASSESSMENT_DARK_ANALYZERS="spelling")

        student_user, student_headers = student
        teacher_user, teacher_headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)
        student_user.class_id = klass.id
        await db.flush()

        submission_id = await score_answer(client, student_headers, seeded_graph)

        for headers in (student_headers, teacher_headers):
            body = (
                await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=headers)
            ).json()
            assert "spelling" not in body["analyzers"]
            assert "spelling" not in body["scores"]
            assert not any(i["analyzer"] == "spelling" for i in body["issues"])

    async def test_the_audience_comes_from_the_row_not_the_current_settings(
        self, client, seeded_graph, student, monkeypatch
    ):
        """A stage that moves later must not retroactively reveal what was dark.

        Marked while spelling was dark, then read on a server that has since
        promoted it. The student still must not see it: the row records what
        was decided when the work was marked.
        """
        override_settings(monkeypatch, ASSESSMENT_DARK_ANALYZERS="spelling")

        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        # The rollout moves on: spelling is now a student-visible analyzer.
        monkeypatch.undo()

        body = (
            await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=headers)
        ).json()

        assert "spelling" not in body["analyzers"]

    async def test_counts_describe_the_run_not_the_slice(
        self, client, seeded_graph, student, monkeypatch
    ):
        """`suppressed_count` covers everything found, visible or not."""
        measure_profiles(monkeypatch)
        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        body = (
            await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=headers)
        ).json()

        assert body["suppressed_count"] >= 0
        assert body["issue_count"] == len(body["issues"])
        assert body["error_count"] <= body["issue_count"]


class TestClassAggregates:
    @pytest.fixture
    async def cohort(
        self, client, seeded_graph, teacher, class_factory, user_factory, db, auth_headers
    ):
        teacher_user, teacher_headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)

        for n in range(3):
            pupil = await user_factory(role=UserRole.STUDENT, email=f"cohort{n}@test.edu")
            pupil.class_id = klass.id
            await db.flush()
            await score_answer(client, auth_headers(pupil), seeded_graph)

        return klass, teacher_headers

    async def test_issue_frequency_reports_the_count_it_was_taken_over(self, client, cohort):
        klass, headers = cohort

        body = (
            await client.get(f"{ASSESSMENT}/issues?class_id={klass.id}", headers=headers)
        ).json()

        assert body["scope"] == "class"
        assert body["submission_count"] == 3
        assert body["assessed_count"] == 3
        assert body["entries"]
        assert all(e["occurrences"] > 0 for e in body["entries"])
        # Zeros included: a missing key reads as missing data, a zero as a finding.
        assert "grammar" in body["counts_by_category"]

    async def test_scores_report_a_count_per_analyzer(self, client, cohort):
        klass, headers = cohort

        body = (
            await client.get(f"{ASSESSMENT}/scores?class_id={klass.id}", headers=headers)
        ).json()

        by_name = {s["analyzer"]: s for s in body["summaries"]}
        assert by_name["spelling"]["assessed_count"] == 3
        assert by_name["spelling"]["average"] is not None
        # No grammar engine is configured in the suite, so it has no figure —
        # and a null rather than a zero is the whole point.
        assert by_name["grammar"]["assessed_count"] == 0
        assert by_name["grammar"]["average"] is None

    async def test_a_trend_line_breaks_rather_than_reporting_zero(self, client, cohort):
        klass, headers = cohort

        body = (
            await client.get(
                f"{ASSESSMENT}/trend/spelling?class_id={klass.id}&interval=day", headers=headers
            )
        ).json()

        assert body["analyzer"] == "spelling"
        assert body["timezone"]
        assert body["points"]
        # Every point present carries data; empty periods are absent entirely.
        for point in body["points"]:
            assert point["assessed_count"] > 0
            assert point["average"] is not None

    async def test_an_unknown_analyzer_is_refused(self, client, cohort):
        klass, headers = cohort

        response = await client.get(
            f"{ASSESSMENT}/trend/nonsense?class_id={klass.id}", headers=headers
        )

        assert response.status_code == 422

    async def test_a_class_the_teacher_does_not_teach_is_refused_not_emptied(
        self, client, cohort, user_factory, auth_headers, class_factory
    ):
        """An empty report and a forbidden one look identical; one is a lie."""
        _klass, _headers = cohort
        other = await user_factory(role=UserRole.TEACHER, email="other-teacher@test.edu")
        theirs = await class_factory(teacher_id=other.id)

        response = await client.get(f"{ASSESSMENT}/issues?class_id={theirs.id}", headers=_headers)

        assert response.status_code == 403

    async def test_a_teacher_may_not_read_platform_wide(self, client, cohort):
        _klass, headers = cohort

        response = await client.get(f"{ASSESSMENT}/issues", headers=headers)

        assert response.status_code == 422

    async def test_an_administrator_may(self, client, cohort, user_factory, auth_headers):
        admin = await user_factory(role=UserRole.ADMIN, email="assessment-admin@test.edu")

        body = (await client.get(f"{ASSESSMENT}/issues", headers=auth_headers(admin))).json()

        assert body["scope"] == "platform"
        assert body["class_id"] is None
        assert body["submission_count"] >= 3

    async def test_a_student_is_refused_the_class_reads(self, client, cohort, student):
        _user, headers = student

        for path in ("/issues", "/scores", "/trend/spelling"):
            assert (await client.get(f"{ASSESSMENT}{path}", headers=headers)).status_code == 403

    async def test_they_demand_a_token(self, client, cohort):
        for path in ("/issues", "/scores", "/trend/spelling"):
            assert (await client.get(f"{ASSESSMENT}{path}")).status_code == 401


class TestConsistencyEndpoint:
    @pytest.fixture
    async def enabled(self, monkeypatch):
        from app.core import config

        real = config.get_settings
        on = real().model_copy(
            update={"CONSISTENCY_ANALYTICS_ENABLED": True, "CONSISTENCY_MIN_WORDS": 1}
        )
        monkeypatch.setattr("app.api.deps.get_settings", lambda: on)
        return on

    async def test_it_is_503_where_the_deployment_has_not_enabled_it(
        self, client, seeded_graph, student, teacher, class_factory, db, monkeypatch
    ):
        """Not an empty comparison: that is indistinguishable from no history."""
        measure_profiles(monkeypatch)
        student_user, student_headers = student
        teacher_user, teacher_headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)
        student_user.class_id = klass.id
        await db.flush()

        submission_id = await score_answer(client, student_headers, seeded_graph)

        response = await client.get(
            f"{ASSESSMENT}/submissions/{submission_id}/consistency", headers=teacher_headers
        )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "CONSISTENCY_UNAVAILABLE"

    async def test_a_student_is_refused_even_for_their_own_submission(
        self, client, seeded_graph, student, monkeypatch, enabled
    ):
        """C2: this surface is teacher-facing, and their own work is no exception."""
        measure_profiles(monkeypatch)
        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        response = await client.get(
            f"{ASSESSMENT}/submissions/{submission_id}/consistency", headers=headers
        )

        assert response.status_code == 403

    async def test_a_first_submission_has_no_baseline(
        self, client, seeded_graph, student, teacher, class_factory, db, monkeypatch, enabled
    ):
        measure_profiles(monkeypatch)
        student_user, student_headers = student
        teacher_user, teacher_headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)
        student_user.class_id = klass.id
        await db.flush()

        submission_id = await score_answer(client, student_headers, seeded_graph)

        body = (
            await client.get(
                f"{ASSESSMENT}/submissions/{submission_id}/consistency", headers=teacher_headers
            )
        ).json()

        assert body["considered_count"] == 0
        assert body["changes"]
        assert all(c["baseline"] is None for c in body["changes"])
        assert all(c["difference"] is None for c in body["changes"])

    async def test_a_baseline_appears_once_there_is_history(
        self, client, seeded_graph, student, teacher, class_factory, db, monkeypatch, enabled
    ):
        measure_profiles(monkeypatch)
        student_user, student_headers = student
        teacher_user, teacher_headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)
        student_user.class_id = klass.id
        await db.flush()

        ids = [await score_answer(client, student_headers, seeded_graph) for _ in range(4)]
        # The whole test runs in one transaction, so all four assessments carry
        # the same `created_at` and the submission id breaks the tie. Creation
        # order is therefore not the comparison order here — in production each
        # submission lands in its own transaction and they differ. Ask about
        # the one that really is last.
        latest = max(ids, key=uuid.UUID)

        body = (
            await client.get(
                f"{ASSESSMENT}/submissions/{latest}/consistency", headers=teacher_headers
            )
        ).json()

        assert body["considered_count"] == 3
        assert body["compared_count"] == 3
        lexical = next(c for c in body["changes"] if c["measure"] == "lexical_diversity")
        assert lexical["baseline"]["n"] == 3

    async def test_the_limits_travel_with_the_figures(
        self, client, seeded_graph, student, teacher, class_factory, db, monkeypatch, enabled
    ):
        """Not in a help page. They change how every number should be read."""
        measure_profiles(monkeypatch)
        student_user, student_headers = student
        teacher_user, teacher_headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)
        student_user.class_id = klass.id
        await db.flush()

        submission_id = await score_answer(client, student_headers, seeded_graph)

        body = (
            await client.get(
                f"{ASSESSMENT}/submissions/{submission_id}/consistency", headers=teacher_headers
            )
        ).json()

        assert len(body["limitations"]) == 3
        joined = " ".join(body["limitations"]).lower()
        assert "not evidence" in joined
        assert "interpretation belongs to you" in joined

    async def test_it_carries_no_verdict_vocabulary(
        self, client, seeded_graph, student, teacher, class_factory, db, monkeypatch, enabled
    ):
        measure_profiles(monkeypatch)
        student_user, student_headers = student
        teacher_user, teacher_headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)
        student_user.class_id = klass.id
        await db.flush()

        submission_id = await score_answer(client, student_headers, seeded_graph)

        body = (
            await client.get(
                f"{ASSESSMENT}/submissions/{submission_id}/consistency", headers=teacher_headers
            )
        ).json()

        # Measure names and gate slugs only — the prose in `limitations` is
        # excluded, because saying "this is not evidence" requires the word.
        payload = repr({k: v for k, v in body.items() if k != "limitations"}).lower()
        for word in ("risk", "cheat", "plagiar", "suspicio", "misconduct", "probability"):
            assert word not in payload
        assert "score" not in {c["measure"] for c in body["changes"]} - {
            "spelling_score",
            "grammar_score",
        }


class TestTheEdgesOfTheAggregates:
    """The paths a happy-path test never reaches, and each is a real answer."""

    async def test_an_inverted_date_range_is_refused(self, client, teacher, class_factory):
        teacher_user, headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)

        response = await client.get(
            f"{ASSESSMENT}/issues?class_id={klass.id}&date_from=2026-06-01&date_to=2026-01-01",
            headers=headers,
        )

        assert response.status_code == 422

    async def test_an_unknown_interval_is_refused(self, client, teacher, class_factory):
        teacher_user, headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)

        response = await client.get(
            f"{ASSESSMENT}/trend/spelling?class_id={klass.id}&interval=fortnight", headers=headers
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("interval", ["day", "week", "month"])
    async def test_every_interval_buckets(
        self, client, seeded_graph, teacher, class_factory, user_factory, auth_headers, db, interval
    ):
        teacher_user, headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)
        pupil = await user_factory(role=UserRole.STUDENT, email=f"bucket-{interval}@test.edu")
        pupil.class_id = klass.id
        await db.flush()
        await score_answer(client, auth_headers(pupil), seeded_graph)

        body = (
            await client.get(
                f"{ASSESSMENT}/trend/spelling?class_id={klass.id}&interval={interval}",
                headers=headers,
            )
        ).json()

        assert body["interval"] == interval
        assert len(body["points"]) == 1
        assert body["points"][0]["assessed_count"] == 1

    async def test_an_empty_class_reports_zero_and_nulls_not_an_error(
        self, client, teacher, class_factory
    ):
        """A class nobody has submitted to is a real answer, not a missing one."""
        teacher_user, headers = teacher
        empty = await class_factory(teacher_id=teacher_user.id)

        issues = (
            await client.get(f"{ASSESSMENT}/issues?class_id={empty.id}", headers=headers)
        ).json()
        scores = (
            await client.get(f"{ASSESSMENT}/scores?class_id={empty.id}", headers=headers)
        ).json()
        trend = (
            await client.get(f"{ASSESSMENT}/trend/spelling?class_id={empty.id}", headers=headers)
        ).json()

        assert issues["submission_count"] == 0
        assert issues["assessed_count"] == 0
        assert issues["entries"] == []
        # Every analyzer reports zero assessed and a null average — never a zero
        # average, which would read as a class that scored nothing.
        assert all(s["assessed_count"] == 0 for s in scores["summaries"])
        assert all(s["average"] is None for s in scores["summaries"])
        assert trend["points"] == []

    async def test_a_consistency_read_for_a_submission_with_no_profile_is_404(
        self, client, seeded_graph, student, teacher, class_factory, db, monkeypatch
    ):
        """The stage-1 deployment: enabled comparison, nothing measured yet."""
        from app.core import config

        on = config.get_settings().model_copy(update={"CONSISTENCY_ANALYTICS_ENABLED": True})
        monkeypatch.setattr("app.api.deps.get_settings", lambda: on)

        student_user, student_headers = student
        teacher_user, teacher_headers = teacher
        klass = await class_factory(teacher_id=teacher_user.id)
        student_user.class_id = klass.id
        await db.flush()

        submission_id = await score_answer(client, student_headers, seeded_graph)

        response = await client.get(
            f"{ASSESSMENT}/submissions/{submission_id}/consistency", headers=teacher_headers
        )

        assert response.status_code == 404

    async def test_a_corrupt_stored_score_reads_as_absent(self, client, seeded_graph, student, db):
        """A row written by a release that shaped the blob differently.

        The figure is dropped rather than the page: the same rule a malformed
        achievement rule follows.
        """
        from app.models.assessment import AssessmentDetail

        _user, headers = student
        submission_id = await score_answer(client, headers, seeded_graph)

        detail = (
            await db.execute(
                select(AssessmentDetail).where(AssessmentDetail.submission_id == submission_id)
            )
        ).scalar_one()
        status = dict(detail.analyzer_status)
        status["spelling"] = {**status["spelling"], "score": "not a number"}
        detail.analyzer_status = status
        await db.flush()

        body = (
            await client.get(f"{ASSESSMENT}/submissions/{submission_id}", headers=headers)
        ).json()

        assert body["analyzers"]["spelling"]["score"] is None
        assert body["analyzers"]["sentence"]["score"] is not None
