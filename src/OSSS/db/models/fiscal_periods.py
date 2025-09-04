from __future__ import annotations

from datetime import date
from typing import List, Optional, ClassVar

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin


class FiscalPeriod(UUIDMixin, TimestampMixin, Base):
    """
    A period within a fiscal year (e.g., month 1..12). We associate periods to fiscal years
    via the natural-key integer 'year_number' instead of a DB-level FK, then define a
    view-only relationship to FiscalYear using an explicit primaryjoin.
    """
    __tablename__ = "fiscal_periods"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_teaching_learning_accountability; "
        "description=Stores fiscal periods records for the application. "
        "References related entities via: fiscal year. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores fiscal periods records for the application. "
            "References related entities via: fiscal year. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores fiscal periods records for the application. "
            "References related entities via: fiscal year. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    # Natural-key reference to FiscalYear.year (not a DB FK)
    year_number = mapped_column(
        sa.Integer,
        sa.ForeignKey("fiscal_years.year", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    period_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 1..12 or 1..13
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.false())

    # View-only relationship that joins on the natural key
    fiscal_year = relationship("FiscalYear", back_populates="periods", lazy="joined")


    # Example other relationship that might exist
    entries: Mapped[List["JournalEntry"]] = relationship("JournalEntry", back_populates="period")