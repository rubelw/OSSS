# src/OSSS/db/models/work_assignments.py
from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from .common_enums import AssignmentStatus
from .events import Event
from .workers import Worker


class WorkAssignment(UUIDMixin, Base):
    __tablename__ = "work_assignments"

    event_id:  Mapped[str]        = mapped_column(GUID(), ForeignKey("events.id", ondelete="CASCADE"),  nullable=False, index=True)
    worker_id: Mapped[str]        = mapped_column(GUID(), ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, index=True)
    role:      Mapped[str | None] = mapped_column(sa.String(128))
    stipend_cents: Mapped[int | None] = mapped_column(sa.Integer)
    status:    Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignment_status", native_enum=False),
        nullable=False,
        default=AssignmentStatus.pending,
    )

    assigned_at:  Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), default=datetime.utcnow)
    checked_in_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    completed_at:  Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))

    # relationships
    event:  Mapped[Event]  = relationship("Event")
    worker: Mapped[Worker] = relationship("Worker", backref="assignments")
