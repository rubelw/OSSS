# src/OSSS/db/models/orders.py
from __future__ import annotations

from typing import Optional, List, ClassVar
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols
from .common_enums import OrderStatus  # ✅ shared enum


class Order(UUIDMixin, Base):
    __tablename__ = "orders"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores orders records for the application. "
        "References related entities via: event, purchaser user. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores orders records for the application. "
            "References related entities via: event, purchaser user. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores orders records for the application. "
                "References related entities via: event, purchaser user. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "10 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    # --- FKs (GUID everywhere; add indexes for joins) -------------------------
    school_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purchaser_user_id: Mapped[Optional[str]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )

    # --- buyer info (new) -----------------------------------------------------
    buyer_name: Mapped[Optional[str]] = mapped_column(sa.String(255))
    buyer_email: Mapped[Optional[str]] = mapped_column(sa.String(255))

    # --- amounts / status -----------------------------------------------------
    total_cents: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=text("0")
    )  # keep cents + server_default
    currency: Mapped[str] = mapped_column(
        sa.String(8), nullable=False, server_default=text("'USD'")
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", native_enum=False),
        nullable=False,
        default=OrderStatus.pending,  # python-side default
    )
    external_ref: Mapped[Optional[str]] = mapped_column(
        sa.String(255)
    )  # payment provider id
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    # --- timestamps -----------------------------------------------------------
    created_at, updated_at = ts_cols()

    # --- relationships --------------------------------------------------------
    event: Mapped["Event"] = relationship("Event", back_populates="orders")

    tickets: Mapped[List["Ticket"]] = relationship(
        "Ticket",
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    line_items: Mapped[list["OrderLineItem"]] = relationship(
        "OrderLineItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderLineItem(UUIDMixin, Base):
    __tablename__ = "order_line_items"

    order_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_type_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("ticket_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    unit_price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # relationships
    order: Mapped[Order] = relationship("Order", back_populates="line_items")
    ticket_type: Mapped["TicketType"] = relationship(
        "TicketType", back_populates="order_line_items"
    )
