
from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, DateTime, Date, Enum, ForeignKey
from .common import Base, TimestampMixin, OrderStatus

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey

class School(Base):
    __tablename__ = "schools"
    id: Mapped[str] = mapped_column(String, primary_key=True)

class Sport(Base):
    __tablename__ = "sports"
    id: Mapped[str] = mapped_column(String, primary_key=True)

class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"))
    sport_id: Mapped[str] = mapped_column(String, ForeignKey("sports.id"))

class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"))

class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"))
    team_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("teams.id"), nullable=True)


class TicketType(TimestampMixin, Base):
    __tablename__ = "ticket_types"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="USD")
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime)

class Pass(TimestampMixin, Base):
    __tablename__ = "passes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    price_cents: Mapped[Optional[int]] = mapped_column(Integer)
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_to: Mapped[Optional[date]] = mapped_column(Date)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer)

class TicketOrder(TimestampMixin, Base):
    __tablename__ = "ticket_orders"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"), nullable=False)
    buyer_name: Mapped[Optional[str]] = mapped_column(String)
    buyer_email: Mapped[Optional[str]] = mapped_column(String)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="order_status", native_enum=False))

class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(String, ForeignKey("ticket_orders.id"), nullable=False)
    ticket_type_id: Mapped[str] = mapped_column(String, ForeignKey("ticket_types.id"), nullable=False)
    event_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("events.id"))
    qr_code: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="order_status", native_enum=False))
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    order: Mapped[TicketOrder] = relationship(backref="tickets")
