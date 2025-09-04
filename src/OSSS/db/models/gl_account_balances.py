from __future__ import annotations

from decimal import Decimal
from typing import Optional, Dict, Any, ClassVar
import sqlalchemy as sa
import uuid
from sqlalchemy import (
    String,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Index,
    DateTime,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from OSSS.db.base import Base, UUIDMixin, GUID


class GlAccountBalance(UUIDMixin, Base):
    __tablename__ = "gl_account_balances"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=business_accounting; "
        "description=Stores gl account balances records for the application. "
        "References related entities via: account, fiscal period. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores gl account balances records for the application. "
            "References related entities via: account, fiscal period. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores gl account balances records for the application. "
            "References related entities via: account, fiscal period. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    # Use GUID()/UUID to match referenced PK types
    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("gl_accounts.id", ondelete="CASCADE"), nullable=False
    )
    fiscal_period_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("fiscal_periods.id", ondelete="CASCADE"), nullable=False
    )

    begin_balance: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0"))
    debit_total:   Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0"))
    credit_total:  Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0"))
    end_balance:   Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0"))

    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
