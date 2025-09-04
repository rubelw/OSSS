from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class TicketType(UUIDMixin, Base):
    __tablename__ = "ticket_types"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores ticket types records for the application. "
        "Key attributes include name. "
        "References related entities via: event. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "11 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores ticket types records for the application. "
            "Key attributes include name. "
            "References related entities via: event. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores ticket types records for the application. "
            "Key attributes include name. "
            "References related entities via: event. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }

    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)  # e.g., General, Student, VIP
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    quantity_total: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    quantity_sold: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    sales_starts_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    sales_ends_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at, updated_at = ts_cols()

    # ✅ add the FK to events
    event_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        sa.ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event: Mapped["Event"] = relationship("Event", back_populates="ticket_types")

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="ticket_type")

    order_line_items: Mapped[list["OrderLineItem"]] = relationship(
        "OrderLineItem",
        back_populates="ticket_type",
        cascade="all, delete-orphan",
    )