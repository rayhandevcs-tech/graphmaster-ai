"""Idempotent seed data.

Shipped as a seeding command rather than as migrations so a development
database can be reseeded without inventing a new migration revision each time.
Every seeder upserts by natural key, so running it repeatedly is safe.
"""

from app.db.seed.runner import seed_all

__all__ = ["seed_all"]
