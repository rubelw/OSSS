from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class IepPlan(UUIDMixin, Base):
    __tablename__ = "iep_plans"

    special_ed_case_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("special_education_cases.id", ondelete="CASCADE"), nullable=False)
    effective_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    effective_end: Mapped[Optional[date]] = mapped_column(sa.Date)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
