from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class TestResult(UUIDMixin, Base):
    __tablename__ = "test_results"

    administration_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("test_administrations.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    scale_score: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2))
    percentile: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))
    performance_level: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("administration_id", "student_id", name="uq_test_result_student"),)
