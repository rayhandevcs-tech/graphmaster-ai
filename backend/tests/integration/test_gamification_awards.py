"""The award engine against a real database.

These exercise ``GamificationService.on_submission_scored`` directly rather
than through the analysis endpoint: the questions here are about what a
*history* of scored work earns, and driving each attempt through spaCy would
make the suite slow and tie the assertions to whatever the rubric awards today.

The constraints being relied on — the daily streak index and the achievement
uniqueness constraint — are real, so these need PostgreSQL rather than fakes.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.gamification.periods import platform_today
from app.models.enums import Gender, UserRole
from app.models.gamification import Achievement, UserAchievement, UserBadge, XPEvent
from app.repositories.gamification import (
    AchievementRepository,
    BadgeRepository,
    XPRepository,
)
from app.repositories.submission import SubmissionRepository
from app.repositories.user import UserRepository
from app.services.gamification import GamificationService

pytestmark = pytest.mark.anyio


@pytest.fixture
def gamification(db):
    return GamificationService(
        XPRepository(db),
        AchievementRepository(db),
        BadgeRepository(db),
        SubmissionRepository(db),
        UserRepository(db),
    )


@pytest.fixture
async def student(user_factory):
    return await user_factory(role=UserRole.STUDENT, gender=Gender.FEMALE)


@pytest.fixture
async def graph(graph_factory, student, user_factory):
    teacher = await user_factory(role=UserRole.TEACHER, email="author@test.edu")
    return await graph_factory(created_by=teacher.id)


async def award(gamification, db, *, student, graph, factory, **score_kwargs):
    """Score one submission and run the engine over it."""
    submission = await factory(user=student, graph=graph, **score_kwargs)
    await db.refresh(submission, ["score"])
    return await gamification.on_submission_scored(submission, submission.score, student=student)


async def xp_total(db, student) -> int:
    stmt = select(func.coalesce(func.sum(XPEvent.amount), 0)).where(XPEvent.user_id == student.id)
    return int((await db.execute(stmt)).scalar_one())


# ── Base XP ──────────────────────────────────────────────────────────────────


async def test_every_scored_submission_earns_the_base_award(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    result = await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        final_score=40.0,
    )

    assert {"reason": "submission", "amount": 20} in result.xp_breakdown
    assert not any(e["reason"] == "high_score_bonus" for e in result.xp_breakdown)


async def test_a_high_score_earns_the_bonus_on_top(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    result = await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        final_score=88.0,
    )

    reasons = {e["reason"]: e["amount"] for e in result.xp_breakdown}
    assert reasons["submission"] == 20
    assert reasons["high_score_bonus"] == 30


async def test_the_bonus_threshold_is_inclusive(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """80.0 exactly is a high score; a student on the boundary is not penalised."""
    result = await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        final_score=80.0,
    )

    assert any(e["reason"] == "high_score_bonus" for e in result.xp_breakdown)


async def test_the_cached_total_matches_the_ledger(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """`users.total_xp` is a cache; the ledger is the truth."""
    await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        final_score=95.0,
    )

    assert student.total_xp == await xp_total(db, student)


# ── Streaks ──────────────────────────────────────────────────────────────────


async def test_a_first_submission_earns_no_streak_bonus(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """There is nothing to continue on day one."""
    result = await award(
        gamification, db, student=student, graph=graph, factory=scored_submission_factory
    )

    assert result.streak_days == 1
    assert not any(e["reason"] == "streak_bonus" for e in result.xp_breakdown)


async def test_practising_the_next_day_extends_the_streak_and_pays_the_bonus(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    today = platform_today(gamification.settings.PLATFORM_TIMEZONE)
    student.last_activity_date = today - timedelta(days=1)
    student.current_streak_days = 1
    await db.flush()

    result = await award(
        gamification, db, student=student, graph=graph, factory=scored_submission_factory
    )

    assert result.streak_days == 2
    assert {"reason": "streak_bonus", "amount": 50} in result.xp_breakdown


async def test_a_second_submission_the_same_day_does_not_pay_the_bonus_twice(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """Otherwise the daily bonus is farmable by resubmitting."""
    today = platform_today(gamification.settings.PLATFORM_TIMEZONE)
    student.last_activity_date = today - timedelta(days=1)
    student.current_streak_days = 3
    await db.flush()

    first = await award(
        gamification, db, student=student, graph=graph, factory=scored_submission_factory
    )
    second = await award(
        gamification, db, student=student, graph=graph, factory=scored_submission_factory
    )

    assert any(e["reason"] == "streak_bonus" for e in first.xp_breakdown)
    assert not any(e["reason"] == "streak_bonus" for e in second.xp_breakdown)
    assert second.streak_days == 4


async def test_returning_after_a_gap_restarts_the_streak_without_a_bonus(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """Paying it here would reward breaking a streak as much as keeping one."""
    today = platform_today(gamification.settings.PLATFORM_TIMEZONE)
    student.last_activity_date = today - timedelta(days=9)
    student.current_streak_days = 8
    student.longest_streak_days = 8
    await db.flush()

    result = await award(
        gamification, db, student=student, graph=graph, factory=scored_submission_factory
    )

    assert result.streak_days == 1
    assert not any(e["reason"] == "streak_bonus" for e in result.xp_breakdown)
    assert student.longest_streak_days == 8


async def test_the_daily_index_refuses_a_second_bonus_for_the_same_day(
    db, student, seeded_gamification
):
    """The backstop against a read-then-write race, asserted directly."""
    xp = XPRepository(db)
    today = date(2026, 8, 24)

    first = await xp.record_once_per_day(
        user_id=student.id, amount=50, reason="streak_bonus", event_date=today
    )
    second = await xp.record_once_per_day(
        user_id=student.id, amount=50, reason="streak_bonus", event_date=today
    )

    assert first is not None
    assert second is None
    # The refusal must not have poisoned the transaction: the session is still
    # usable, which is the whole point of the savepoint around the insert.
    assert await xp.total_for(student.id) == 50


async def test_the_daily_index_only_constrains_streak_bonuses(db, student, seeded_gamification):
    """Two submissions on one day both earn their base XP."""
    xp = XPRepository(db)
    today = date(2026, 8, 24)

    await xp.record(user_id=student.id, amount=20, reason="submission", event_date=today)
    await xp.record(user_id=student.id, amount=20, reason="submission", event_date=today)

    assert await xp.total_for(student.id) == 40


async def test_the_bonus_is_skipped_when_the_day_is_already_paid_for(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """The streak continues, but today's 50 XP has already been banked.

    Reachable when two submissions race: the streak counters say "continued"
    while the daily index has already accepted one bonus. The award must be
    skipped, not retried and not fatal.
    """
    today = platform_today(gamification.settings.PLATFORM_TIMEZONE)
    student.last_activity_date = today - timedelta(days=1)
    student.current_streak_days = 2
    await db.flush()
    await XPRepository(db).record(
        user_id=student.id, amount=50, reason="streak_bonus", event_date=today
    )

    result = await award(
        gamification, db, student=student, graph=graph, factory=scored_submission_factory
    )

    assert not any(e["reason"] == "streak_bonus" for e in result.xp_breakdown)
    assert result.streak_days == 3


# ── Badges ───────────────────────────────────────────────────────────────────


async def test_the_tier_badge_is_attached_to_the_submission(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    result = await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        reward_tier="crown",
    )

    assert result.badge["reward_tier"] == "crown"
    assert (await db.execute(select(func.count(UserBadge.id)))).scalar_one() == 1


async def test_badges_are_re_awardable_unlike_achievements(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """One badge per submission, so a tally rather than a flag."""
    for _ in range(3):
        await award(
            gamification,
            db,
            student=student,
            graph=graph,
            factory=scored_submission_factory,
            reward_tier="flower",
        )

    counts = await BadgeRepository(db).counts_for(student.id)
    assert counts["flower"] == 3


# ── Achievements ─────────────────────────────────────────────────────────────


async def test_awarding_the_same_submission_twice_is_refused_by_the_database(
    db, student, graph, scored_submission_factory, seeded_gamification
):
    """`user_badges.submission_id` is unique, so this needs no check in code."""
    badges = BadgeRepository(db)
    submission = await scored_submission_factory(user=student, graph=graph)
    flower = await badges.for_tier("flower")

    first = await badges.award(user_id=student.id, badge_id=flower.id, submission_id=submission.id)
    second = await badges.award(user_id=student.id, badge_id=flower.id, submission_id=submission.id)

    assert first is not None
    assert second is None
    # The refusal was absorbed by a savepoint, so the session still works.
    assert await badges.counts_for(student.id) == {"flower": 1}


async def test_unlocking_a_held_achievement_twice_is_refused_by_the_database(
    db, student, seeded_gamification
):
    """FR-8.8's single award, enforced by UNIQUE (user_id, achievement_id)."""
    from sqlalchemy import select

    achievements = AchievementRepository(db)
    first_steps = (
        await db.execute(select(Achievement).where(Achievement.code == "first_submission"))
    ).scalar_one()

    first = await achievements.unlock(user_id=student.id, achievement_id=first_steps.id)
    second = await achievements.unlock(user_id=student.id, achievement_id=first_steps.id)

    assert first is not None
    assert second is None
    assert await achievements.unlocked_ids(student.id) == {first_steps.id}


async def test_the_first_submission_unlocks_first_steps_and_pays_its_reward(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    result = await award(
        gamification, db, student=student, graph=graph, factory=scored_submission_factory
    )

    codes = {a["code"] for a in result.new_achievements}
    assert "first_submission" in codes
    assert {"reason": "achievement", "amount": 50} in result.xp_breakdown


async def test_an_achievement_unlocks_only_once(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    first = await award(
        gamification, db, student=student, graph=graph, factory=scored_submission_factory
    )
    second = await award(
        gamification, db, student=student, graph=graph, factory=scored_submission_factory
    )

    assert "first_submission" in {a["code"] for a in first.new_achievements}
    assert "first_submission" not in {a["code"] for a in second.new_achievements}

    # One row, not two — the uniqueness constraint is what guarantees it.
    held = (
        await db.execute(
            select(func.count(UserAchievement.id))
            .select_from(UserAchievement)
            .join(Achievement, Achievement.id == UserAchievement.achievement_id)
            .where(
                UserAchievement.user_id == student.id,
                Achievement.code == "first_submission",
            )
        )
    ).scalar_one()
    assert held == 1


async def test_a_female_student_earns_graph_queen_and_never_graph_king(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """Each student has exactly one reachable crown achievement (FR-7.2)."""
    result = await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        reward_tier="crown",
    )

    codes = {a["code"] for a in result.new_achievements}
    assert "graph_queen" in codes
    assert "graph_king" not in codes


async def test_a_male_student_earns_graph_king(
    gamification, db, graph, user_factory, scored_submission_factory, seeded_gamification
):
    male = await user_factory(role=UserRole.STUDENT, gender=Gender.MALE, email="him@test.edu")

    result = await award(
        gamification,
        db,
        student=male,
        graph=graph,
        factory=scored_submission_factory,
        reward_tier="crown",
    )

    codes = {a["code"] for a in result.new_achievements}
    assert "graph_king" in codes
    assert "graph_queen" not in codes


async def test_three_strong_attempts_in_a_row_unlock_vocabulary_master(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    codes: set[str] = set()
    for _ in range(3):
        result = await award(
            gamification,
            db,
            student=student,
            graph=graph,
            factory=scored_submission_factory,
            vocabulary_percentage=93.0,
            reward_tier="crown",
        )
        codes |= {a["code"] for a in result.new_achievements}

    assert "vocabulary_master" in codes


async def test_a_weak_attempt_between_strong_ones_breaks_the_run(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    codes: set[str] = set()
    for percentage in (95.0, 30.0, 95.0):
        result = await award(
            gamification,
            db,
            student=student,
            graph=graph,
            factory=scored_submission_factory,
            vocabulary_percentage=percentage,
        )
        codes |= {a["code"] for a in result.new_achievements}

    assert "vocabulary_master" not in codes


async def test_describing_all_four_chart_types_unlocks_well_rounded(
    gamification,
    db,
    student,
    graph_factory,
    user_factory,
    scored_submission_factory,
    seeded_gamification,
):
    teacher = await user_factory(role=UserRole.TEACHER, email="four@test.edu")
    codes: set[str] = set()

    for graph_type in ("line", "bar", "pie", "area"):
        graph = await graph_factory(created_by=teacher.id, graph_type=graph_type)
        result = await award(
            gamification, db, student=student, graph=graph, factory=scored_submission_factory
        )
        codes |= {a["code"] for a in result.new_achievements}

    assert "well_rounded" in codes


# ── Levels ───────────────────────────────────────────────────────────────────


async def test_the_level_is_recomputed_after_achievement_xp_not_before(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """First Steps pays 50 XP, which is exactly level 2 on its own.

    Recomputing the level before achievements were evaluated would leave the
    student on level 1 holding enough XP for level 2 until their next
    submission — a level-up animation that fires a day late.
    """
    result = await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        final_score=40.0,
    )

    assert result.level_before == 1
    assert result.leveled_up
    assert result.level_after >= 2
    assert result.level_after == student.current_level


async def test_a_level_up_is_reported_only_when_the_boundary_is_crossed(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        final_score=40.0,
    )
    second = await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        final_score=40.0,
    )

    assert second.level_before == second.level_after
    assert not second.leveled_up


# ── Administrative corrections ───────────────────────────────────────────────


async def test_an_adjustment_offsets_rather_than_edits(
    gamification,
    db,
    student,
    graph,
    scored_submission_factory,
    seeded_gamification,
    user_factory,
):
    admin = await user_factory(role=UserRole.ADMIN, email="root@test.edu")
    await award(
        gamification,
        db,
        student=student,
        graph=graph,
        factory=scored_submission_factory,
        final_score=95.0,
    )
    before = student.total_xp

    await gamification.adjust_xp(
        user_id=student.id, amount=-30, note="Duplicate award corrected", admin=admin
    )

    events = (
        (await db.execute(select(XPEvent).where(XPEvent.user_id == student.id))).scalars().all()
    )
    # The original awards are all still there — nothing was edited or removed.
    assert len(events) >= 2
    assert any(e.amount == -30 and e.reason == "manual_adjustment" for e in events)
    assert student.total_xp == before - 30


async def test_an_adjustment_of_zero_is_refused(
    gamification, db, student, seeded_gamification, user_factory
):
    """A no-op entry would clutter the ledger with nothing to explain."""
    from app.core.exceptions import ValidationError

    admin = await user_factory(role=UserRole.ADMIN, email="root0@test.edu")

    with pytest.raises(ValidationError):
        await gamification.adjust_xp(user_id=student.id, amount=0, note="Nothing", admin=admin)


async def test_an_adjustment_without_a_reason_is_refused_at_the_service_too(
    gamification, db, student, seeded_gamification, user_factory
):
    """The schema rejects a blank note first; the rule belongs here as well.

    An unexplained correction is indistinguishable from tampering once the
    ledger is used as research evidence, so the guard cannot live only in the
    layer a seeding script or a test can bypass.
    """
    from app.core.exceptions import ValidationError

    admin = await user_factory(role=UserRole.ADMIN, email="root3@test.edu")

    with pytest.raises(ValidationError):
        await gamification.adjust_xp(user_id=student.id, amount=-10, note="   ", admin=admin)


async def test_an_adjustment_cannot_take_a_student_below_zero(
    gamification, db, student, seeded_gamification, user_factory
):
    """`users.total_xp` carries a non-negative CHECK; this is the friendly refusal."""
    from app.core.exceptions import ValidationError

    admin = await user_factory(role=UserRole.ADMIN, email="root2@test.edu")

    with pytest.raises(ValidationError):
        await gamification.adjust_xp(user_id=student.id, amount=-500, note="Too far", admin=admin)


async def test_the_event_date_uses_the_platform_timezone(
    gamification, db, student, graph, scored_submission_factory, seeded_gamification
):
    """The ledger's day is the cohort's day, not the server's UTC day."""
    await award(gamification, db, student=student, graph=graph, factory=scored_submission_factory)

    today = platform_today(gamification.settings.PLATFORM_TIMEZONE)
    dates = (
        (await db.execute(select(XPEvent.event_date).where(XPEvent.user_id == student.id)))
        .scalars()
        .all()
    )
    assert dates
    assert set(dates) == {today}
