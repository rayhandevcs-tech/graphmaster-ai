"""Portable column types.

The production database is PostgreSQL, but the unit test suite runs against
SQLite so it needs no server. These aliases render as the native PostgreSQL
type where one exists and fall back to a portable equivalent elsewhere.
"""

from __future__ import annotations

from sqlalchemy import JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on PostgreSQL (indexable, binary), plain JSON elsewhere.
JSONType = JSON().with_variant(JSONB, "postgresql")

# UUID on PostgreSQL, CHAR(32) elsewhere. SQLAlchemy 2.0's native handling.
GUID = Uuid(as_uuid=True)
