from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class HREmployee(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "hr_employees"

    person_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("persons.id", ondelete="SET NULL"))
    employee_no: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)
    primary_school_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("schools.id", ondelete="SET NULL"))

    # matches earlier migration column name (segment, not value):
    department_segment_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="SET NULL"))

    employment_type: Mapped[Optional[str]] = mapped_column(sa.String(16))  # full_time, part_time, etc.
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'active'"))
    hire_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    termination_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    assignments: Mapped[list["HRPositionAssignment"]] = relationship(
        "HRPositionAssignment", back_populates="employee", cascade="all, delete-orphan"
    )
