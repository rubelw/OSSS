from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, CheckConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB


def ts_cols():
    return (
        mapped_column(sa.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
        mapped_column(sa.TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

class Activity(UUIDMixin, Base):
    """
    A club, team, group (e.g., Drama Club, Robotics, Soccer).
    Events can optionally belong to an Activity.
    """
    __tablename__ = "activities"

    school_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default=text("true"), nullable=False)
    created_at, updated_at = ts_cols()

    events: Mapped[list["Event"]] = relationship(back_populates="activity", cascade="all, delete-orphan")

class Event(UUIDMixin, Base):
    __tablename__ = "events"

    school_id: Mapped[str] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    activity_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("activities.id", ondelete="SET NULL"))

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    starts_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    venue: Mapped[Optional[str]] = mapped_column(sa.String(255))
    status: Mapped[str] = mapped_column(sa.String(16), server_default=text("'draft'"), nullable=False)  # draft|published|cancelled
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at, updated_at = ts_cols()

    activity: Mapped[Optional[Activity]] = relationship(back_populates="events")
    ticket_types: Mapped[list["TicketType"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship(back_populates="event", cascade="all, delete-orphan")

class TicketType(UUIDMixin, Base):
    __tablename__ = "ticket_types"
    __table_args__ = (
        UniqueConstraint("event_id", "name", name="uq_event_tickettype_name"),
        CheckConstraint("price_cents >= 0", name="ck_ticket_price_nonneg"),
        CheckConstraint("quantity_total >= 0", name="ck_ticket_qty_total_nonneg"),
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

class Order(UUIDMixin, Base):
    __tablename__ = "orders"

    event_id: Mapped[str] = mapped_column(GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    purchaser_user_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    # money kept as cents to avoid floats
    total_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    currency: Mapped[str] = mapped_column(sa.String(8), nullable=False, server_default=text("'USD'"))
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=text("'pending'"))  # pending|paid|cancelled|refunded
    external_ref: Mapped[Optional[str]] = mapped_column(sa.String(255))  # payment provider id
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at, updated_at = ts_cols()

    event: Mapped[Event] = relationship(back_populates="orders")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="order", cascade="all, delete-orphan")

class Ticket(UUIDMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("ticket_type_id", "serial_no", name="uq_ticket_serial_per_type"),
        CheckConstraint("price_cents >= 0", name="ck_ticket_price_nonneg"),
    )

    order_id: Mapped[str] = mapped_column(GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    ticket_type_id: Mapped[str] = mapped_column(GUID(), ForeignKey("ticket_types.id", ondelete="RESTRICT"), nullable=False)
    serial_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 1..N per type
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    holder_person_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="SET NULL"))
    qr_code: Mapped[Optional[str]] = mapped_column(sa.String(128))  # token/nonce
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=text("'issued'"))  # issued|checked_in|void
    issued_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    created_at, updated_at = ts_cols()

    order: Mapped[Order] = relationship(back_populates="tickets")
    ticket_type: Mapped[TicketType] = relationship(back_populates="tickets")

class TicketScan(UUIDMixin, Base):
    __tablename__ = "ticket_scans"

    ticket_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    scanned_by_user_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    scanned_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    result: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # ok|duplicate|invalid|void
    location: Mapped[Optional[str]] = mapped_column(sa.String(255))
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at, updated_at = ts_cols()
