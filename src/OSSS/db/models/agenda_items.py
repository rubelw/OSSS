from __future__ import annotations

import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class AgendaItem(UUIDMixin, Base):
    __tablename__ = "agenda_items"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    linked_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    linked_objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    time_allocated: Mapped[Optional[int]] = mapped_column(sa.Integer)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="agenda_items", lazy="joined")

    # self-referential hierarchy
    parent: Mapped[Optional["AgendaItem"]] = relationship(
        "AgendaItem",
        remote_side="AgendaItem.id",
        back_populates="children",
        foreign_keys=[parent_id],
        lazy="selectin",
    )
    children: Mapped[List["AgendaItem"]] = relationship(
        "AgendaItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id],
        passive_deletes=True,
        lazy="selectin",
        order_by="AgendaItem.position",
    )

    __table_args__ = (
        sa.Index("ix_agenda_items_meeting", "meeting_id"),
        sa.Index("ix_agenda_items_parent", "parent_id"),
    )
