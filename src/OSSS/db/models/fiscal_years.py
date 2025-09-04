from __future__ import annotations

from datetime import date
from typing import List, ClassVar

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin


class FiscalYear(UUIDMixin, TimestampMixin, Base):
    """
    Represents a fiscal year, e.g., 2024.
    """
    __tablename__ = "fiscal_years"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_finance; "
        "description=Stores fiscal years records for the application. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores fiscal years records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores fiscal years records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    # Natural key, e.g., 2024
    year: Mapped[int] = mapped_column(sa.Integer, nullable=False, unique=True, index=True)

    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.false())

    # Backref to periods. NOTE: back_populates points to 'fiscal_year' on FiscalPeriod
    periods: Mapped[List["FiscalPeriod"]] = relationship(
        "FiscalPeriod",
        back_populates="fiscal_year",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

