# src/OSSS/db/models/tickets.py
from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from .common_enums import OrderStatus


class Ticket(UUIDMixin, Base):
    __tablename__ = "tickets"

    # FKs
    order_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    ticket_type_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("ticket_types.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    event_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    # attrs
    qr_code: Mapped[str | None] = mapped_column(sa.String(128))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", native_enum=False),
        nullable=False, default=OrderStatus.paid
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=datetime.utcnow
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True)
    )

    # relationships (string targets avoid import cycles)
    order: Mapped["Order"] = relationship("Order", back_populates="tickets")
    ticket_type: Mapped["TicketType"] = relationship("TicketType", back_populates="tickets")
    event: Mapped["Event"] = relationship("Event")
