"""Idempotent seeding.

Every seeder upserts by natural key (``code`` or ``lemma``), so running this
repeatedly against a populated database updates rather than duplicates.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.seed.data import (
    ACHIEVEMENTS,
    AVATARS,
    BADGES,
    VOCABULARY_CATEGORIES,
    VOCABULARY_ITEMS,
)
from app.models import (
    Achievement,
    Avatar,
    Badge,
    VocabularyCategory,
    VocabularyItem,
)

logger = get_logger(__name__)


async def seed_avatars(db: AsyncSession) -> int:
    existing = {a.code: a for a in (await db.execute(select(Avatar))).scalars()}
    created = 0
    for row in AVATARS:
        avatar = existing.get(row["code"])
        if avatar is None:
            db.add(Avatar(**row))
            created += 1
        else:
            for field, value in row.items():
                setattr(avatar, field, value)
    await db.flush()
    logger.info("Avatars: %d created, %d updated", created, len(AVATARS) - created)
    return created


async def seed_vocabulary(db: AsyncSession) -> tuple[int, int]:
    existing_categories = {
        c.code: c for c in (await db.execute(select(VocabularyCategory))).scalars()
    }
    categories_created = 0
    for row in VOCABULARY_CATEGORIES:
        category = existing_categories.get(row["code"])
        if category is None:
            category = VocabularyCategory(**row)
            db.add(category)
            existing_categories[row["code"]] = category
            categories_created += 1
        else:
            category.name = row["name"]
            category.description = row["description"]
            category.display_order = row["display_order"]

    # Flush so newly created categories have IDs before items reference them.
    await db.flush()

    existing_items = {i.lemma: i for i in (await db.execute(select(VocabularyItem))).scalars()}
    items_created = 0
    for row in VOCABULARY_ITEMS:
        category = existing_categories[row["category"]]
        term = row["term"]
        # A term containing whitespace is a phrase; derived rather than
        # hand-maintained so the flag can never disagree with the term itself.
        is_phrase = row.get("is_phrase", " " in term)

        item = existing_items.get(row["lemma"])
        if item is None:
            db.add(
                VocabularyItem(
                    category_id=category.id,
                    term=term,
                    lemma=row["lemma"],
                    is_phrase=is_phrase,
                    weight=row.get("weight", 1.00),
                    is_active=True,
                )
            )
            items_created += 1
        else:
            item.category_id = category.id
            item.term = term
            item.is_phrase = is_phrase
            item.weight = row.get("weight", 1.00)

    await db.flush()
    logger.info(
        "Vocabulary: %d/%d categories, %d/%d items created",
        categories_created,
        len(VOCABULARY_CATEGORIES),
        items_created,
        len(VOCABULARY_ITEMS),
    )
    return categories_created, items_created


async def seed_badges(db: AsyncSession) -> int:
    existing = {b.code: b for b in (await db.execute(select(Badge))).scalars()}
    created = 0
    for row in BADGES:
        badge = existing.get(row["code"])
        if badge is None:
            db.add(Badge(**row))
            created += 1
        else:
            for field, value in row.items():
                setattr(badge, field, value)
    await db.flush()
    logger.info("Badges: %d created", created)
    return created


async def seed_achievements(db: AsyncSession) -> int:
    existing = {a.code: a for a in (await db.execute(select(Achievement))).scalars()}
    created = 0
    for row in ACHIEVEMENTS:
        achievement = existing.get(row["code"])
        if achievement is None:
            db.add(Achievement(**row))
            created += 1
        else:
            for field, value in row.items():
                setattr(achievement, field, value)
    await db.flush()
    logger.info("Achievements: %d created", created)
    return created


async def seed_all(db: AsyncSession) -> dict[str, int]:
    """Seed all reference data. Safe to run repeatedly."""
    avatars = await seed_avatars(db)
    categories, items = await seed_vocabulary(db)
    badges = await seed_badges(db)
    achievements = await seed_achievements(db)
    await db.commit()
    return {
        "avatars": avatars,
        "vocabulary_categories": categories,
        "vocabulary_items": items,
        "badges": badges,
        "achievements": achievements,
    }
