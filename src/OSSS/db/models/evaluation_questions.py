from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationQuestion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_questions"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores evaluation questions records for the application. "
        "References related entities via: section. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores evaluation questions records for the application. "
            "References related entities via: section. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores evaluation questions records for the application. "
            "References related entities via: section. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    section_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_sections.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    type: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # scale|text|multi
    scale_min: Mapped[Optional[int]] = mapped_column(sa.Integer)
    scale_max: Mapped[Optional[int]] = mapped_column(sa.Integer)
    weight: Mapped[Optional[float]] = mapped_column(sa.Float)

    section: Mapped["EvaluationSection"] = relationship("EvaluationSection", back_populates="questions")


