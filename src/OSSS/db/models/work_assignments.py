from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from OSSS.db.base import Base, UUIDMixin, GUID
from .common_enums import AssignmentStatus

if TYPE_CHECKING:
    from .workers import Worker          # typing only
    from .events import Event            # typing only

class WorkAssignment(UUIDMixin, Base):
    __tablename__ = "work_assignments"

    # FKs (ensure these exist!)
    event_id:  Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("events.id"),  nullable=False, index=True)
    worker_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workers.id"), nullable=False, index=True)

    stipend_cents: Mapped[int | None] = mapped_column(sa.Integer)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignment_status", native_enum=False),
        nullable=False,
        default=AssignmentStatus.pending,
    )

    assigned_at:   Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    checked_in_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    completed_at:  Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))

    # relationships (use strings; pair with back_populates on the other side)
    event:  Mapped["Event"]  = relationship("Event", back_populates="assignments", lazy="joined")
    worker: Mapped["Worker"] = relationship("Worker", back_populates="assignments", lazy="joined")
