from __future__ import annotations

from decimal import Decimal
from typing import Optional, Dict, Any
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

    __table_args__ = (
        UniqueConstraint("account_id", "fiscal_period_id", name="uq_balance_acct_period"),
        Index("ix_balances_acct", "account_id"),
        Index("ix_balances_period", "fiscal_period_id"),
    )
