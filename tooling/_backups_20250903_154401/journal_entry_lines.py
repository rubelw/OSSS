from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class JournalEntryLine(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "journal_entry_lines"

    entry_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False)

    line_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255))
    debit: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")
    credit: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")
    segment_overrides: Mapped[Optional[dict]] = mapped_column(JSONB())

    entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["GLAccount"] = relationship("GLAccount", back_populates="lines")
