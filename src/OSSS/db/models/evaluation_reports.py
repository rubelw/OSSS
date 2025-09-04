from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationReport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_reports"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores evaluation reports records for the application. "
        "References related entities via: cycle, file. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores evaluation reports records for the application. "
            "References related entities via: cycle, file. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores evaluation reports records for the application. "
            "References related entities via: cycle, file. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    cycle_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[Optional[dict]] = mapped_column(JSONB())
    generated_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    file_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("files.id", ondelete="SET NULL"))

    cycle: Mapped["EvaluationCycle"] = relationship("EvaluationCycle", back_populates="reports")


