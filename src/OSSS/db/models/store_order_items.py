# src/OSSS/db/models/store_order_items.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class StoreOrderItem(UUIDMixin, Base):
    __tablename__ = "store_order_items"
    __table_args__ = (
        sa.CheckConstraint("quantity > 0", name="ck_store_item_qty_pos"),
        sa.CheckConstraint("price_cents >= 0", name="ck_store_item_price_nonneg"),
    )

    order_id:   Mapped[str] = mapped_column(
        GUID(), ForeignKey("store_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("store_products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity:    Mapped[int] = mapped_column(sa.Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # snapshot

    # relationships
    order:   Mapped["StoreOrder"]   = relationship("StoreOrder", backref="items")
    product: Mapped["StoreProduct"] = relationship("StoreProduct")
