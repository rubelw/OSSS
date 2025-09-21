# src/OSSS/db/models/tickets.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, ClassVar
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB  # JSONB kept in case you add attrs later
from ._helpers import ts_cols


class Ticket(UUIDMixin, Base):
    __tablename__ = "tickets"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=division_of_technology_data; "
        "description=Stores tickets records for the application. "
        "Key attributes include serial_no. "
        "References related entities via: holder person, order, ticket type. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "12 column(s) defined. "
        "Primary key is `id`. "
        "3 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores tickets records for the application. "
            "Key attributes include serial_no. "
            "References related entities via: holder person, order, ticket type. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores tickets records for the application. "
                "Key attributes include serial_no. "
                "References related entities via: holder person, order, ticket type. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "12 column(s) defined. "
                "Primary key is `id`. "
                "3 foreign key field(s) detected."
            ),
        },
    }

    # --- columns --------------------------------------------------------------

    ticket_type_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("ticket_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,  # ✅ add index as in your integrated version
    )

    serial_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 1..N per type

    price_cents: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        server_default=text("0"),
    )

    holder_person_id: Mapped[str | None] = mapped_column(  # ✅ py3.11 union syntax
        GUID(),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )

    qr_code: Mapped[str | None] = mapped_column(sa.String(128))  # token/nonce

    status: Mapped[str] = mapped_column(  # issued|checked_in|void
        sa.String(16),
        nullable=False,
        server_default=text("'issued'"),
    )

    issued_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    checked_in_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True)
    )

    # keep your standard audit timestamps
    created_at, updated_at = ts_cols()

    order_id: Mapped[str] = mapped_column(  # ✅ keep GUID + index (string type with GUID())
        GUID(),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- relationships --------------------------------------------------------

    # Use string targets to avoid import cycles.
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="tickets",
        lazy="joined",
    )

    ticket_type: Mapped["TicketType"] = relationship(
        "TicketType",
        back_populates="tickets",
    )
