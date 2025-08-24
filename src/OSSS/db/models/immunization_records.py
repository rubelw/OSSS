from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class ImmunizationRecord(UUIDMixin, Base):
    __tablename__ = "immunization_records"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    immunization_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("immunizations.id", ondelete="CASCADE"), nullable=False)
    date_administered: Mapped[date] = mapped_column(sa.Date, nullable=False)
    dose_number: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "immunization_id", "date_administered", name="uq_immunization_record"),)
