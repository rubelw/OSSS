from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class Activity(UUIDMixin, Base):
    """
    A club, team, group (e.g., Drama Club, Robotics, Soccer).
    Events can optionally belong to an Activity.
    """
    __tablename__ = "activities"

    school_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default=text("true"), nullable=False)
    created_at, updated_at = ts_cols()

    events: Mapped[list["Event"]] = relationship(back_populates="activity", cascade="all, delete-orphan")
