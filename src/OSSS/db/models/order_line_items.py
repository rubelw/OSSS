from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols  # if you use the common timestamp helper

class OrderLineItem(UUIDMixin, Base):
    __tablename__ = "order_line_items"
    __table_args__ = (
        sa.CheckConstraint("quantity > 0", name="ck_oli_qty_pos"),
    )

    order_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    ticket_type_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("ticket_types.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # common created/updated columns (if you're using them elsewhere)
    created_at, updated_at = ts_cols()

    # relationships
    order: Mapped["Order"] = relationship(
        "Order", back_populates="line_items"
    )
    ticket_type: Mapped["TicketType"] = relationship(
        "TicketType", back_populates="order_line_items"
    )
