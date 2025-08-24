from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class School(UUIDMixin, Base):
    __tablename__ = "schools"

    organization_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    school_code: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    nces_school_id: Mapped[Optional[str]] = mapped_column(sa.Text)
    building_code: Mapped[Optional[str]] = mapped_column(sa.Text)
    type: Mapped[Optional[str]] = mapped_column(sa.Text)
    timezone: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )
