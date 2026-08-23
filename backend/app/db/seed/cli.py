"""Seeding entry point.

Usage:
    python -m app.db.seed.cli
"""

from __future__ import annotations

import asyncio

from app.core.logging import configure_logging, get_logger
from app.db.seed.runner import seed_all
from app.db.session import SessionFactory, engine

logger = get_logger(__name__)


async def main() -> None:
    configure_logging()
    async with SessionFactory() as session:
        result = await seed_all(session)
    await engine.dispose()
    total = sum(result.values())
    logger.info("Seeding complete: %d new rows %s", total, result)


if __name__ == "__main__":
    asyncio.run(main())
