# src/OSSS/db/models/order_line_items.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols  # keep if you're using the shared timestamp helper


class OrderLineItem(UUIDMixin, Base):
    """
    Stores order line items and ties an order to a ticket type, with quantity and unit price.
    """
    __tablename__ = "order_line_items"
    __table_args__ = (
        sa.CheckConstraint("quantity > 0", name="ck_oli_qty_pos"),
        sa.CheckConstraint("unit_price_cents >= 0", name="ck_oli_unit_price_nonneg"),
        {
            "comment": (
                "Stores order line items records for the application. References related entities via: order, ticket type. "
                "Includes standard audit timestamps (created_at, updated_at). 6+ column(s) defined. "
                "Primary key is `id`. 2 foreign key field(s) detected."
            ),
            "info": {
                "description": (
                    "Stores order line items records for the application. References related entities via: order, ticket type. "
                    "Includes standard audit timestamps (created_at, updated_at)."
                )
            },
        },
    )

    # FKs
    order_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    ticket_type_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("ticket_types.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )

    # payload
    quantity: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # common created/updated columns
    created_at, updated_at = ts_cols()

    # relationships (string targets to avoid import cycles)
    order: Mapped["Order"] = relationship("Order", back_populates="line_items")
    ticket_type: Mapped["TicketType"] = relationship("TicketType", back_populates="order_line_items")
