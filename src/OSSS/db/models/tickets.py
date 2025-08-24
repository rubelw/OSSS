from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Ticket(UUIDMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        sa.UniqueConstraint("ticket_type_id", "serial_no", name="uq_ticket_serial_per_type"),
        sa.CheckConstraint("price_cents >= 0", name="ck_ticket_price_nonneg"),
    )

    order_id: Mapped[str] = mapped_column(GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    ticket_type_id: Mapped[str] = mapped_column(GUID(), ForeignKey("ticket_types.id", ondelete="RESTRICT"), nullable=False)
    serial_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 1..N per type
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    holder_person_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="SET NULL"))
    qr_code: Mapped[Optional[str]] = mapped_column(sa.String(128))  # token/nonce
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=text("'issued'"))  # issued|checked_in|void
    issued_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    created_at, updated_at = ts_cols()

    order: Mapped[Order] = relationship(back_populates="tickets")
    ticket_type: Mapped[TicketType] = relationship(back_populates="tickets")
