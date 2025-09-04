from __future__ import annotations

import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class AgendaItem(UUIDMixin, Base):
    __tablename__ = "agenda_items"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores agenda items records for the application. "
        "Key attributes include title. "
        "References related entities via: linked objective, linked policy, meeting, parent. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "11 column(s) defined. "
        "Primary key is `id`. "
        "4 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores agenda items records for the application. "
            "Key attributes include title. "
            "References related entities via: linked objective, linked policy, meeting, parent. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "4 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores agenda items records for the application. "
            "Key attributes include title. "
            "References related entities via: linked objective, linked policy, meeting, parent. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "4 foreign key field(s) detected."
        ),
        },
    }


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
