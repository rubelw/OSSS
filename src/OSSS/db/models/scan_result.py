# src/OSSS/db/models/scan_result.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class ScanResult(UUIDMixin, Base):
    __tablename__ = "scan_results"

    # Core fields
    ok: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    ticket_id: Mapped[Optional[str]] = mapped_column(
        GUID(), ForeignKey("tickets.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(),
        onupdate=sa.func.now(), nullable=False
    )

    # Relationships
    ticket: Mapped[Optional["Ticket"]] = relationship("Ticket")
