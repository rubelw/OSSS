# src/OSSS/db/models/consequences.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, GUID, UUIDMixin


class Consequence(UUIDMixin, Base):
    __tablename__ = "consequences"

    incident_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("incident_participants.id", ondelete="CASCADE"), nullable=False
    )
    consequence_code: Mapped[str] = mapped_column(
        sa.Text, sa.ForeignKey("consequence_types.code", ondelete="RESTRICT"), nullable=False
    )

    start_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    end_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
    )
