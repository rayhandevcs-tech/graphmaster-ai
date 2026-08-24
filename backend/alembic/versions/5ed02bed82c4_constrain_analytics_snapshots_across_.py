"""constrain analytics snapshots across nullable scope columns

`uq_analytics_snapshot` covered (scope, class_id, user_id, period_start), and
two of those four columns are NULL for most scopes: `class_id` and `user_id`
for the platform scope, `user_id` for a class. Under PostgreSQL's default rule
NULLs never compare equal, so the constraint permitted unlimited duplicate
snapshots for every scope except `student`.

Replaced with the same index declared NULLS NOT DISTINCT. This is the same hole
that was silently listing every student twice on the global leaderboard, in a
table that has not been written to yet — fixed now rather than after it starts
holding rows.

Hand-written: Alembic's autogenerate does not detect a change to an index's
NULL-handling any more than it detects a predicate.

Revision ID: 5ed02bed82c4
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5ed02bed82c4"
down_revision: str | None = "3192a974dff1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "uq_analytics_snapshot"
COLUMNS = ["scope", "class_id", "user_id", "period_start"]


def upgrade() -> None:
    op.drop_constraint(NAME, "analytics_snapshots", type_="unique")
    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX {NAME} ON analytics_snapshots "
            f"({', '.join(COLUMNS)}) NULLS NOT DISTINCT"
        )
    )


def downgrade() -> None:
    op.drop_index(NAME, table_name="analytics_snapshots")
    op.create_unique_constraint(NAME, "analytics_snapshots", COLUMNS)
