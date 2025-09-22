"""
SQLAlchemy model for StoreOrderItem with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar
import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, mapped_column, Mapped
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class StoreOrderItem(UUIDMixin, Base):
    __tablename__ = "store_order_items"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores store order item records for the application. "
        "Key attributes include quantity and price. "
        "References related entities via: store_order, store_product. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores store order item records for the application. "
            "Key attributes include quantity and price. "
            "References related entities via: store_order, store_product. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores store order item records for the application. "
                "Key attributes include quantity and price. "
                "References related entities via: store_order, store_product. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    order_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("store_orders.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("store_products.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )

    # quantity and unit price captured at time of order
    quantity: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)

    # Back-populates that match the canonical names above
    order: Mapped["StoreOrder"] = relationship(
        "StoreOrder",
        back_populates="items",
        lazy="selectin",
    )
    product: Mapped["StoreProduct"] = relationship(
        "StoreProduct",
        back_populates="order_items",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<StoreOrderItem id={self.id} order_id={self.order_id} product_id={self.product_id}>"