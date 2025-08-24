from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class CICAgendaItem(UUIDMixin, Base):
    __tablename__ = "cic_agenda_items"

    meeting_id   = sa.Column(GUID(), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    parent_id    = sa.Column(GUID(), ForeignKey("cic_agenda_items.id", ondelete="SET NULL"))
    position     = sa.Column(sa.Integer, nullable=False, server_default=text("0"))
    title        = sa.Column(sa.Text, nullable=False)
    description  = sa.Column(sa.Text)
    time_allocated_minutes = sa.Column(sa.Integer)
    subject_id   = sa.Column(GUID(), ForeignKey("subjects.id", ondelete="SET NULL"))
    course_id    = sa.Column(GUID(), ForeignKey("courses.id",  ondelete="SET NULL"))

    created_at, updated_at = ts_cols()

    __table_args__ = (UniqueConstraint("meeting_id", "position", name="uq_cic_agenda_position"),)

    meeting = relationship("CICMeeting", back_populates="agenda_items")

    # Self-referential tree
    parent = relationship(
        "CICAgendaItem",
        remote_side=lambda: [CICAgendaItem.id],
        back_populates="children",
        foreign_keys=lambda: [CICAgendaItem.parent_id],
    )
    children = relationship(
        "CICAgendaItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [CICAgendaItem.parent_id],
        passive_deletes=True,
    )

    motions = relationship("CICMotion", back_populates="agenda_item", cascade="all, delete-orphan")
