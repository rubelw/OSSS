from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class TestAdministration(UUIDMixin, Base):
    __tablename__ = "test_administrations"

    test_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("standardized_tests.id", ondelete="CASCADE"), nullable=False)
    administration_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    school_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
