"""Analysis endpoints."""

from __future__ import annotations

import pytest

from app.models.enums import RewardTier, UserRole

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("spacy_model")]

PREVIEW = "/api/v1/analysis/graphs/{id}/preview"
TARGETS = "/api/v1/analysis/graphs/{id}/targets"
ENGINE = "/api/v1/analysis/engine"
RUBRIC = "/api/v1/analysis/rubric"


@pytest.fixture
async def teacher(user_factory, auth_headers):
    user = await user_factory(role=UserRole.TEACHER, email="teacher@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def admin(user_factory, auth_headers):
    user = await user_factory(role=UserRole.ADMIN, email="admin@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def student(user_factory, auth_headers):
    user = await user_factory(role=UserRole.STUDENT, email="student@test.edu")
    return user, auth_headers(user)


@pytest.fixture
async def line_graph(graph_factory, seeded_vocabulary, teacher):
    """A published line graph with eight required and one bonus target."""
    user, _ = teacher
    required = ["increase", "rise", "decrease", "fluctuate", "stable", "peak", "high than"]
    return await graph_factory(
        created_by=user.id,
        graph_type="line",
        targets=[seeded_vocabulary[lemma] for lemma in required],
        optional_targets=[seeded_vocabulary["soar"]],
    )


# ── Engine status ────────────────────────────────────────────────────────────


async def test_engine_reports_the_deployed_rubric(client, teacher, settings):
    _, headers = teacher
    response = await client.get(ENGINE, headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["available"] is True
    assert body["rubric"]["vocabulary_weight"] == settings.VOCABULARY_WEIGHT
    assert body["rubric"]["writing_weight"] == settings.WRITING_WEIGHT
    assert body["rubric"]["tier_thresholds"]["crown"] == settings.TIER_CROWN_MIN
    assert body["pipeline"]["available"] is True


async def test_engine_version_is_reported(client, teacher):
    _, headers = teacher
    assert (await client.get(ENGINE, headers=headers)).json()["engine_version"]


async def test_engine_requires_authentication(client):
    assert (await client.get(ENGINE)).status_code == 401


# ── The student-safe rubric ──────────────────────────────────────────────────

#: Everything the student rubric is allowed to carry. Asserted as an exact set
#: rather than key by key: a field added to the response later is then a
#: failing test that someone has to look at, which is the only way a rule about
#: what must *not* be published survives a later sprint.
STUDENT_RUBRIC_KEYS = {"vocabulary_weight", "writing_weight", "target_word_count"}


async def test_student_rubric_reports_the_deployed_weights(client, student, settings):
    _, headers = student
    response = await client.get(RUBRIC, headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["vocabulary_weight"] == settings.VOCABULARY_WEIGHT
    assert body["writing_weight"] == settings.WRITING_WEIGHT
    assert body["target_word_count"] == {
        "min": settings.TARGET_WORD_COUNT_MIN,
        "max": settings.TARGET_WORD_COUNT_MAX,
    }


async def test_student_rubric_carries_nothing_else(client, student):
    """No tier threshold, no engine version, no pipeline, no vocabulary.

    The point of the endpoint is what it leaves out. A threshold turns writing
    into aiming at a number; the pipeline and version are deployment facts; and
    the target list would turn description into transcription.
    """
    _, headers = student
    body = (await client.get(RUBRIC, headers=headers)).json()

    assert set(body) == STUDENT_RUBRIC_KEYS

    serialised = str(body)
    for forbidden in ("tier", "crown", "engine_version", "pipeline", "term"):
        assert forbidden not in serialised


async def test_student_rubric_is_open_to_every_signed_in_role(client, student, teacher, admin):
    for _, headers in (student, teacher, admin):
        assert (await client.get(RUBRIC, headers=headers)).status_code == 200


async def test_student_rubric_requires_authentication(client):
    assert (await client.get(RUBRIC)).status_code == 401


async def test_student_rubric_agrees_with_the_engine_a_teacher_sees(client, student, teacher):
    """One configuration, two audiences — never two numbers.

    A student told the weighting is 70/30 while the server scores on something
    else is worse than a student told nothing, so the shared field is asserted
    equal rather than merely present in both.
    """
    _, student_headers = student
    _, teacher_headers = teacher

    published = (await client.get(RUBRIC, headers=student_headers)).json()
    deployed = (await client.get(ENGINE, headers=teacher_headers)).json()["rubric"]

    assert published["vocabulary_weight"] == deployed["vocabulary_weight"]
    assert published["writing_weight"] == deployed["writing_weight"]
    assert published["target_word_count"] == deployed["target_word_count"]


# ── Target resolution ────────────────────────────────────────────────────────


async def test_curated_targets_are_reported_as_curated(client, teacher, line_graph):
    _, headers = teacher
    response = await client.get(TARGETS.format(id=line_graph.id), headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["source"] == "curated"
    assert body["required_count"] == 7
    assert body["optional_count"] == 1


async def test_a_graph_with_no_targets_falls_back_to_the_chart_type(
    client, teacher, graph_factory, seeded_vocabulary
):
    # Publishing is already blocked without required targets, so this is the
    # draft-preview path (FR-5.6).
    user, headers = teacher
    graph = await graph_factory(created_by=user.id, graph_type="pie", is_published=False)

    body = (await client.get(TARGETS.format(id=graph.id), headers=headers)).json()
    assert body["source"] == "default"
    assert body["required_count"] > 0
    # A pie chart is a single snapshot, so movement language is not asked for.
    assert {term["category"] for term in body["terms"]} == {"comparison", "peak", "lowest"}


async def test_a_default_set_stays_small_enough_for_the_crown_to_be_reachable(
    client, teacher, graph_factory, seeded_vocabulary
):
    user, headers = teacher
    graph = await graph_factory(created_by=user.id, graph_type="line", is_published=False)
    assert (await client.get(TARGETS.format(id=graph.id), headers=headers)).json()[
        "required_count"
    ] <= 10


async def test_a_deactivated_term_drops_out_of_the_target_set(
    client, db, teacher, line_graph, seeded_vocabulary
):
    # Terms are soft-deleted so historical scores stay explainable, but a
    # retired term must not keep inflating the denominator of new ones.
    _, headers = teacher
    seeded_vocabulary["fluctuate"].is_active = False
    await db.flush()

    body = (await client.get(TARGETS.format(id=line_graph.id), headers=headers)).json()
    assert body["required_count"] == 6
    assert "fluctuate" not in {t["lemma"] for t in body["terms"]}


async def test_targets_are_not_shown_to_students(client, student, line_graph):
    # The list is the denominator; handed over before writing, the task becomes
    # transcription of a word list rather than description.
    _, headers = student
    assert (await client.get(TARGETS.format(id=line_graph.id), headers=headers)).status_code == 403


async def test_targets_404_for_an_unknown_graph(client, teacher):
    import uuid

    _, headers = teacher
    response = await client.get(TARGETS.format(id=uuid.uuid4()), headers=headers)
    assert response.status_code == 404


# ── Preview ──────────────────────────────────────────────────────────────────


async def test_preview_scores_a_strong_answer(client, teacher, line_graph, strong_answer):
    _, headers = teacher
    response = await client.post(
        PREVIEW.format(id=line_graph.id), json={"text": strong_answer}, headers=headers
    )
    assert response.status_code == 200

    body = response.json()
    assert body["graph_id"] == str(line_graph.id)
    assert body["vocabulary_percentage"] > 50
    assert body["reward_tier"] in {t.value for t in RewardTier}
    assert body["word_count"] > 150
    assert body["engine_version"]


async def test_preview_returns_the_full_result_shape(client, teacher, line_graph, strong_answer):
    _, headers = teacher
    body = (
        await client.post(
            PREVIEW.format(id=line_graph.id), json={"text": strong_answer}, headers=headers
        )
    ).json()

    assert {"headline", "message", "strengths", "improvements", "next_step"} <= set(
        body["feedback"]
    )
    assert set(body["writing_breakdown"]["components"]) == {
        "word_count",
        "lexical_diversity",
        "sentence_structure",
        "overview",
    }
    assert body["category_breakdown"]["increase"]["target_count"] >= 1


async def test_preview_positions_index_the_submitted_text(
    client, teacher, line_graph, strong_answer
):
    _, headers = teacher
    body = (
        await client.post(
            PREVIEW.format(id=line_graph.id), json={"text": strong_answer}, headers=headers
        )
    ).json()

    for term in body["detected_terms"]:
        for start, end in term["positions"]:
            # The client highlights on these offsets without re-running any
            # matching, so they must slice the exact words out of the text it
            # sent.
            assert strong_answer[start:end] in term["matched_forms"]


async def test_preview_of_a_weak_answer_never_humiliates(client, teacher, line_graph, weak_answer):
    _, headers = teacher
    body = (
        await client.post(
            PREVIEW.format(id=line_graph.id), json={"text": weak_answer}, headers=headers
        )
    ).json()

    assert body["reward_tier"] == RewardTier.HAMMER.value
    assert "Keep Practicing! You Can Improve!" in body["feedback"]["message"]
    assert body["feedback"]["strengths"]


async def test_preview_records_nothing(client, db, teacher, line_graph, strong_answer):
    from sqlalchemy import func, select

    from app.models.submission import Score, Submission

    _, headers = teacher
    await client.post(
        PREVIEW.format(id=line_graph.id), json={"text": strong_answer}, headers=headers
    )

    assert (await db.execute(select(func.count()).select_from(Submission))).scalar() == 0
    assert (await db.execute(select(func.count()).select_from(Score))).scalar() == 0


async def test_bonus_terms_are_credited_but_not_counted_in_the_denominator(
    client, teacher, line_graph
):
    _, headers = teacher
    body = (
        await client.post(
            PREVIEW.format(id=line_graph.id),
            json={"text": "Output soared throughout the whole of the period shown."},
            headers=headers,
        )
    ).json()

    assert body["total_target_count"] == 7
    assert body["bonus_terms_used"] == 1


async def test_preview_rejects_an_empty_answer(client, teacher, line_graph):
    _, headers = teacher
    response = await client.post(
        PREVIEW.format(id=line_graph.id), json={"text": "   "}, headers=headers
    )
    assert response.status_code == 422


async def test_preview_rejects_a_missing_answer(client, teacher, line_graph):
    _, headers = teacher
    response = await client.post(PREVIEW.format(id=line_graph.id), json={}, headers=headers)
    assert response.status_code == 422


async def test_preview_rejects_an_over_long_answer(client, teacher, line_graph):
    from app.nlp import MAX_ANALYSIS_CHARS

    _, headers = teacher
    response = await client.post(
        PREVIEW.format(id=line_graph.id),
        json={"text": "x" * (MAX_ANALYSIS_CHARS + 1)},
        headers=headers,
    )
    assert response.status_code == 422


async def test_preview_is_not_open_to_students(client, student, line_graph, strong_answer):
    # Open to students, it would let them iterate a draft against the marker
    # until it scored 100 and only then submit.
    _, headers = student
    response = await client.post(
        PREVIEW.format(id=line_graph.id), json={"text": strong_answer}, headers=headers
    )
    assert response.status_code == 403


async def test_preview_requires_authentication(client, line_graph):
    response = await client.post(PREVIEW.format(id=line_graph.id), json={"text": "Sales rose."})
    assert response.status_code == 401


async def test_preview_404_for_an_unknown_graph(client, teacher):
    import uuid

    _, headers = teacher
    response = await client.post(
        PREVIEW.format(id=uuid.uuid4()), json={"text": "Sales rose."}, headers=headers
    )
    assert response.status_code == 404


async def test_an_admin_may_preview_any_graph(client, admin, line_graph, strong_answer):
    _, headers = admin
    response = await client.post(
        PREVIEW.format(id=line_graph.id), json={"text": strong_answer}, headers=headers
    )
    assert response.status_code == 200


async def test_preview_works_on_an_unpublished_draft(
    client, teacher, graph_factory, seeded_vocabulary
):
    # The whole point is checking a target list before setting the assignment.
    user, headers = teacher
    graph = await graph_factory(
        created_by=user.id,
        is_published=False,
        targets=[seeded_vocabulary["increase"], seeded_vocabulary["fall"]],
    )
    response = await client.post(
        PREVIEW.format(id=graph.id),
        json={"text": "Sales increased and then fell away sharply."},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["vocabulary_percentage"] == 100.0
