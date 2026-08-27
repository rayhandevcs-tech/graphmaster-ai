"""Content models: graphs, the vocabulary library, and per-graph targets."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import Difficulty, GraphType, values

if TYPE_CHECKING:
    from app.models.identity import Class, User
    from app.models.submission import Submission


class Graph(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A practice exercise: a chart for the student to describe."""

    __tablename__ = "graphs"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    graph_type: Mapped[str] = mapped_column(String(16), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)

    # Chart.js-compatible structured data rather than a rendered image, so the
    # chart is crisp at any size, themeable, and exposable as a data table for
    # screen readers. See docs/architecture/02-database-schema.md §3.2.
    chart_data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    creator: Mapped[User] = relationship(back_populates="authored_graphs")
    submissions: Mapped[list[Submission]] = relationship(back_populates="graph")
    target_vocabulary: Mapped[list[GraphTargetVocabulary]] = relationship(
        back_populates="graph", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            f"graph_type IN ({', '.join(repr(v) for v in values(GraphType))})",
            name="graph_type_valid",
        ),
        CheckConstraint(
            f"difficulty IN ({', '.join(repr(v) for v in values(Difficulty))})",
            name="difficulty_valid",
        ),
        Index("ix_graphs_type_difficulty", "graph_type", "difficulty"),
        Index("ix_graphs_is_published", "is_published"),
    )

    def __repr__(self) -> str:
        return f"<Graph {self.title!r} ({self.graph_type})>"


class VocabularyCategory(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One of the seven graph-description vocabulary categories."""

    __tablename__ = "vocabulary_categories"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    items: Mapped[list[VocabularyItem]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<VocabularyCategory {self.code}>"


class VocabularyItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single vocabulary term or phrase. Teacher-editable."""

    __tablename__ = "vocabulary_items"

    category_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("vocabulary_categories.id", ondelete="RESTRICT"), nullable=False
    )
    term: Mapped[str] = mapped_column(String(100), nullable=False)
    # The normalised key detection matches against. For phrases this is the
    # space-joined lemma sequence, e.g. "bottom out" matches "bottomed out".
    lemma: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_phrase: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weight: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=1.00)

    # Soft delete. Historical scores store term references, so removing a row
    # would make a student's past result unexplainable.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    category: Mapped[VocabularyCategory] = relationship(back_populates="items")
    creator: Mapped[User | None] = relationship(back_populates="authored_vocabulary")
    graph_targets: Mapped[list[GraphTargetVocabulary]] = relationship(
        back_populates="vocabulary_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("weight > 0", name="weight_positive"),
        Index("ix_vocabulary_items_category_id", "category_id"),
        Index("ix_vocabulary_items_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<VocabularyItem {self.term!r}>"


class GraphTargetVocabulary(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """The curated target set for one graph.

    This is the denominator of the vocabulary percentage. Scoping it per graph
    rather than to the whole library is what makes the crown tier reachable —
    see docs/PROJECT_PLAN.md §3.2.
    """

    __tablename__ = "graph_target_vocabulary"

    graph_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False
    )
    vocabulary_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("vocabulary_items.id", ondelete="CASCADE"), nullable=False
    )
    # Optional terms are credited in the numerator but excluded from the
    # denominator, letting a teacher offer bonus vocabulary without making the
    # crown tier harder to reach.
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    graph: Mapped[Graph] = relationship(back_populates="target_vocabulary")
    vocabulary_item: Mapped[VocabularyItem] = relationship(back_populates="graph_targets")

    __table_args__ = (
        UniqueConstraint("graph_id", "vocabulary_item_id", name="uq_graph_vocabulary"),
        Index("ix_graph_target_vocabulary_graph_id", "graph_id"),
    )


class Assignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A graph a class has been asked to describe, with an expectation attached.

    The one sentence the product could not say. It had graphs, and it had
    classes, and nothing that joined them — so a teacher could publish work but
    not *set* it, and a student saw a library rather than a task.

    **A section is a class.** A faculty member teaching four sections makes
    four classes, each with its own join code; nothing new was needed for that,
    and an assignment therefore points at exactly one class.

    Deliberately thin. An assignment carries a due date and a label, and
    changes nothing about how work is marked: the rubric, the tier, the XP
    award and the leaderboard behave the same whether a submission belongs to
    one or not. A passed deadline marks a submission late; it never refuses it,
    because refusing the work a student finally sat down to do is the opposite
    of the point.
    """

    __tablename__ = "assignments"

    class_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # RESTRICT, not CASCADE: a graph with work set against it must not vanish
    # underneath the submissions that reference it. Graphs are already
    # undeletable once attempted; this extends the same protection to a graph
    # that has been assigned but not yet attempted.
    graph_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("graphs.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    #: What the teacher said in the lesson — the slide, the handout, the caveat.
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Null means "no deadline", which is a different thing from "overdue".
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    class_: Mapped[Class] = relationship()
    graph: Mapped[Graph] = relationship()
    submissions: Mapped[list[Submission]] = relationship(back_populates="assignment")

    __table_args__ = (
        # The only hot read: this class's open work, soonest first.
        Index("ix_assignments_class_open", "class_id", "is_active", "due_at"),
        # No unique constraint over (class_id, graph_id). Setting the same
        # graph again next term is legitimate, and a partial unique index over
        # `is_active` would stop a teacher reopening work they closed by
        # accident.
    )
