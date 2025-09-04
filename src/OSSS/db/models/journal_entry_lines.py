from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class JournalEntryLine(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "journal_entry_lines"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=business_accounting; "
        "description=Stores journal entry lines records for the application. "
        "References related entities via: account, entry. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores journal entry lines records for the application. "
            "References related entities via: account, entry. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores journal entry lines records for the application. "
            "References related entities via: account, entry. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    entry_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False)

    line_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255))
    debit: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")
    credit: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")
    segment_overrides: Mapped[Optional[dict]] = mapped_column(JSONB())

    entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["GLAccount"] = relationship("GLAccount", back_populates="lines")


