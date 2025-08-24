from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class TicketType(UUIDMixin, Base):
    __tablename__ = "ticket_types"
    __table_args__ = (
        sa.UniqueConstraint("event_id", "name", name="uq_event_tickettype_name"),
        sa.CheckConstraint("price_cents >= 0", name="ck_ticket_price_nonneg"),
        sa.CheckConstraint("quantity_total >= 0", name="ck_ticket_qty_total_nonneg"),
    )

    event_id: Mapped[str] = mapped_column(GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)  # e.g., General, Student, VIP
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    quantity_total: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    quantity_sold: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    sales_starts_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    sales_ends_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at, updated_at = ts_cols()

    event: Mapped[Event] = relationship(back_populates="ticket_types")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="ticket_type")
    order_line_items: Mapped[list["OrderLineItem"]] = relationship(
        "OrderLineItem",
        back_populates="ticket_type",
        cascade="all, delete-orphan",
    )
