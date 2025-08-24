from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class JournalEntry(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (sa.UniqueConstraint("batch_id", "je_no", name="uq_batch_je_no"),)

    batch_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("journal_batches.id", ondelete="CASCADE"), nullable=False)
    fiscal_period_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False)

    je_no: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # unique per batch
    journal_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255))
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'open'"))
    total_debits: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")
    total_credits: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")

    batch: Mapped["JournalBatch"] = relationship("JournalBatch", backref="entries")
    period: Mapped["FiscalPeriod"] = relationship("FiscalPeriod", back_populates="entries")
    lines: Mapped[list["JournalEntryLine"]] = relationship(
        "JournalEntryLine", back_populates="entry", cascade="all, delete-orphan"
    )
