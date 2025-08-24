# src/OSSS/db/models/order_line_items.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols


class OrderLineItem(UUIDMixin, Base):
    __tablename__ = "order_line_items"
    __table_args__ = (
        sa.UniqueConstraint("order_id", "ticket_type_id", name="uq_order_ticket_type"),
        sa.CheckConstraint("quantity > 0", name="ck_lineitem_qty_positive"),
    )

    order_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    ticket_type_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("ticket_types.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    created_at, updated_at = ts_cols()

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="line_items")
    ticket_type: Mapped["TicketType"] = relationship(back_populates="line_items")

    def __repr__(self) -> str:
        return f"<OrderLineItem id={self.id} order_id={self.order_id} ticket_type_id={self.ticket_type_id} qty={self.quantity}>"
