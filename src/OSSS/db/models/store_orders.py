"""
SQLAlchemy model for StoreOrder with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, text, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
import sqlalchemy as sa

if TYPE_CHECKING:
    from .store_order_items import StoreOrderItem


class StoreOrder(UUIDMixin, Base):
    __tablename__ = "store_orders"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores store order records for the application. "
        "Key attributes include user and total price. "
        "References related entities via: user. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores store order records for the application. "
            "Key attributes include user and total price. "
            "References related entities via: user. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores store order records for the application. "
                "Key attributes include user and total price. "
                "References related entities via: user. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    customer_id: Mapped[str | None] = mapped_column(GUID(), index=True)
    status: Mapped[str] = mapped_column(sa.String(32), default="pending", index=True)
    notes: Mapped[str | None] = mapped_column(sa.Text)

    # Python attribute cannot be named "metadata" (reserved by SQLAlchemy).
    # Keep the DB column name as "metadata" for compatibility.
    order_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        default = dict,
        name = "metadata",  # DB column name
        key = "order_metadata",  # Python attribute name
    )

    # Order owns its items
    items: Mapped[list["StoreOrderItem"]] = relationship(
        "StoreOrderItem",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Optional convenience totals
    @property
    def subtotal_cents(self) -> int:
        return sum((it.price_cents or 0) * (it.quantity or 0) for it in self.items)

    def __repr__(self) -> str:
        return f"<StoreOrder id={self.id} status={self.status!r}>"