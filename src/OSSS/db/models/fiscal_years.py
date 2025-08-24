from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class FiscalYear(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fiscal_years"

    year: Mapped[int] = mapped_column(sa.Integer, nullable=False, unique=True)  # e.g., 2024
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))

    periods: Mapped[list["FiscalPeriod"]] = relationship(
        "FiscalPeriod", back_populates="year", cascade="all, delete-orphan"
    )
