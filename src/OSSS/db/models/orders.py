from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

# ⬇️ add this line (it won’t create a cycle because OrderLineItem only uses string refs)
from .order_line_items import OrderLineItem as _OrderLineItem  # noqa: F401


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
    line_items: Mapped[list["OrderLineItem"]] = relationship(
        "OrderLineItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )