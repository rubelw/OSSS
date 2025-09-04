from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class TicketScan(UUIDMixin, Base):
    __tablename__ = "ticket_scans"

    ticket_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    scanned_by_user_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    scanned_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False)
    result: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # ok|duplicate|invalid|void
    location: Mapped[Optional[str]] = mapped_column(sa.String(255))
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at, updated_at = ts_cols()
