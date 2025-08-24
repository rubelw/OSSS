from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class StudentGuardian(Base):
    __tablename__ = "student_guardians"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    guardian_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True)
    custody: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_primary: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))
    contact_order: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
