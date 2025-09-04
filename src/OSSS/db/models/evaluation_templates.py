from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_templates"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores evaluation templates records for the application. "
        "Key attributes include name. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores evaluation templates records for the application. "
            "Key attributes include name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores evaluation templates records for the application. "
            "Key attributes include name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    for_role: Mapped[Optional[str]] = mapped_column(sa.String(80))
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.true())

    sections: Mapped[list["EvaluationSection"]] = relationship(
        "EvaluationSection", back_populates="template", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["EvaluationAssignment"]] = relationship(
        "EvaluationAssignment", back_populates="template", cascade="all, delete-orphan"
    )


