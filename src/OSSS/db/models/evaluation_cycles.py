from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationCycle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_cycles"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores evaluation cycles records for the application. "
        "Key attributes include name. "
        "References related entities via: org. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores evaluation cycles records for the application. "
            "Key attributes include name. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores evaluation cycles records for the application. "
            "Key attributes include name. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    org_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    start_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    end_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    assignments: Mapped[list["EvaluationAssignment"]] = relationship(
        "EvaluationAssignment", back_populates="cycle", cascade="all, delete-orphan"
    )
    reports: Mapped[list["EvaluationReport"]] = relationship(
        "EvaluationReport", back_populates="cycle", cascade="all, delete-orphan"
    )


