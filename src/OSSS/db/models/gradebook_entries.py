from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class GradebookEntry(UUIDMixin, Base):
    __tablename__ = "gradebook_entries"

    assignment_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 3))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    late: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_gradebook_student_assignment"),)
