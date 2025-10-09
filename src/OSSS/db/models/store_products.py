"""
SQLAlchemy model for StoreProduct with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, TYPE_CHECKING

from sqlalchemy import Column, DateTime, String, Integer, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, mapped_column, Mapped
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
import sqlalchemy as sa

if TYPE_CHECKING:
    from .store_order_items import StoreOrderItem


class StoreProduct(UUIDMixin, Base):
    __tablename__ = "store_products"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores store product records for the application. "
        "Key attributes include name and price. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "0 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores store product records for the application. "
            "Key attributes include name and price. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "0 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores store product records for the application. "
                "Key attributes include name and price. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "0 foreign key field(s) detected."
            ),
        },
    }

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    sku: Mapped[str | None] = mapped_column(sa.String(128), unique=True)
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    inventory_qty: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)

    # If you previously had `metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)`
    # rename the Python attribute (e.g., product_metadata), but keep DB column named "metadata".
    product_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        name="metadata",  # DB column remains "metadata"
        key="product_metadata",  # Python attribute is product_metadata
    )

    # Canonical relationship from Product -> OrderItem
    order_items: Mapped[list["StoreOrderItem"]] = relationship(
        "StoreOrderItem",
        back_populates="product",
        lazy="selectin",
        # No delete-orphan here; items are owned by the Order, not the Product.
        cascade="save-update, merge",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<StoreProduct id={self.id} sku={self.sku!r} name={self.name!r}>"