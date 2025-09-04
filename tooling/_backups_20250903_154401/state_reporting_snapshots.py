from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class StateReportingSnapshot(UUIDMixin, Base):
    __tablename__ = "state_reporting_snapshots"

    as_of_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(sa.Text)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
