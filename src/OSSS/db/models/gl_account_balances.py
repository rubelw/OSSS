from __future__ import annotations

from decimal import Decimal
from typing import Optional, Dict, Any

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

from OSSS.db.base import Base, UUIDMixin


class GlAccountBalance(UUIDMixin, Base):
    """
    Mirrors Alembic migration:

      gl_account_balances(
        id UUID PK,
        account_id FK -> gl_accounts.id (CASCADE),
        fiscal_period_id FK -> fiscal_periods.id (CASCADE),
        begin_balance NUMERIC(16,2) DEFAULT 0,
        debit_total  NUMERIC(16,2) DEFAULT 0,
        credit_total NUMERIC(16,2) DEFAULT 0,
        end_balance  NUMERIC(16,2) DEFAULT 0,
        attributes JSONB NULL,
        created_at/updated_at,
        UNIQUE(account_id, fiscal_period_id),
        INDEX account_id, INDEX fiscal_period_id
      )
    """

    __tablename__ = "gl_account_balances"

    # FKs (String(36) to align with your id_col())
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("gl_accounts.id", ondelete="CASCADE"), nullable=False
    )
    fiscal_period_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fiscal_periods.id", ondelete="CASCADE"), nullable=False
    )

    # Amounts
    begin_balance: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, server_default=text("0")
    )
    debit_total: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, server_default=text("0")
    )
    credit_total: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, server_default=text("0")
    )
    end_balance: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, server_default=text("0")
    )

    # Freeform attributes (PostgreSQL)
    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Timestamps (match your *_timestamps(); adjust if you already have a mixin)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("account_id", "fiscal_period_id", name="uq_balance_acct_period"),
        Index("ix_balances_acct", "account_id"),
        Index("ix_balances_period", "fiscal_period_id"),
    )
