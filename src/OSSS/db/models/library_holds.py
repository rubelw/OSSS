from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class LibraryHold(UUIDMixin, Base):
    __tablename__ = "library_holds"

    item_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    placed_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    expires_on: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("item_id", "person_id", name="uq_library_hold"),)
