from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar
import uuid
import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class JournalEntry(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "journal_entries"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_teaching_learning_accountability; "
        "description=Stores journal entries records for the application. "
        "References related entities via: batch, fiscal period. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "11 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores journal entries records for the application. "
            "References related entities via: batch, fiscal period. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores journal entries records for the application. "
            "References related entities via: batch, fiscal period. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }

    fiscal_period_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False)

    je_no: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # unique per batch
    journal_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255))
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'open'"))
    total_debits: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")
    total_credits: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")

    batch_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        sa.ForeignKey("journal_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # relationship to parent batch
    batch: Mapped["JournalBatch"] = relationship(
        "JournalBatch",
        back_populates="entries",
        lazy="joined",
    )

    period: Mapped["FiscalPeriod"] = relationship("FiscalPeriod", back_populates="entries")
    lines: Mapped[list["JournalEntryLine"]] = relationship(
        "JournalEntryLine", back_populates="entry", cascade="all, delete-orphan"
    )