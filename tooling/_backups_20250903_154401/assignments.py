from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Assignment(UUIDMixin, Base):
    __tablename__ = "assignments"

    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("assignment_categories.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    points_possible: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
