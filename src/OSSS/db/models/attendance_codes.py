from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AttendanceCode(Base):
    __tablename__ = "attendance_codes"

    code: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_present: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))
    is_excused: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
