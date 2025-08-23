# src/OSSS/db/models/incidents.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID


class Incident(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "incidents"

    # nullable SET NULL to allow school deletion without removing incidents
    school_id: Mapped[Optional[str]] = mapped_column(
        GUID(), sa.ForeignKey("schools.id", ondelete="SET NULL")
    )

    occurred_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)

    # Behavior codes are stored in a lookup table; keep FK to its natural key
    behavior_code: Mapped[str] = mapped_column(
        sa.Text,
        sa.ForeignKey("behavior_codes.code", ondelete="RESTRICT"),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    __table_args__ = (
        sa.Index("ix_incidents_school", "school_id"),
        sa.Index("ix_incidents_occurred_at", "occurred_at"),
        sa.Index("ix_incidents_behavior", "behavior_code"),
    )
