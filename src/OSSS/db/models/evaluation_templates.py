from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_templates"

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    for_role: Mapped[Optional[str]] = mapped_column(sa.String(80))
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))

    sections: Mapped[list["EvaluationSection"]] = relationship(
        "EvaluationSection", back_populates="template", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["EvaluationAssignment"]] = relationship(
        "EvaluationAssignment", back_populates="template", cascade="all, delete-orphan"
    )
