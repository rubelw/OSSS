from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class GradeScaleBand(UUIDMixin, Base):
    __tablename__ = "grade_scale_bands"

    grade_scale_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("grade_scales.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(sa.Text, nullable=False)
    min_value: Mapped[Decimal] = mapped_column(sa.Numeric(6, 3), nullable=False)
    max_value: Mapped[Decimal] = mapped_column(sa.Numeric(6, 3), nullable=False)
    gpa_points: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(4, 2))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
