from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class HRPositionAssignment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "hr_position_assignments"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=hr_operations_talent; "
        "description=Stores hr position assignments records for the application. "
        "References related entities via: employee, position. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores hr position assignments records for the application. "
            "References related entities via: employee, position. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores hr position assignments records for the application. "
            "References related entities via: employee, position. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    employee_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    position_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_positions.id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    percent: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 2))  # allocation percent
    funding_split: Mapped[Optional[dict]] = mapped_column(JSONB())       # list of {gl_account_id, percent}

    employee: Mapped["HREmployee"] = relationship("HREmployee", back_populates="assignments")
    position: Mapped["HRPosition"] = relationship("HRPosition", back_populates="assignments")


