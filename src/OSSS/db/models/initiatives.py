from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Initiative(UUIDMixin, Base):
    __tablename__ = "initiatives"

    objective_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    due_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))
    priority: Mapped[Optional[str]] = mapped_column(sa.String(16))

    objective: Mapped["Objective"] = relationship("Objective", back_populates="initiatives", lazy="joined")
    owner: Mapped[Optional["User"]] = relationship("User", lazy="joined")  # type: ignore[name-defined]

    __table_args__ = (
        sa.Index("ix_initiatives_objective", "objective_id"),
        sa.Index("ix_initiatives_owner", "owner_id"),
    )
