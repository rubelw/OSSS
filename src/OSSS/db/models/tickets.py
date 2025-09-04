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

class Ticket(UUIDMixin, Base):
    __tablename__ = "tickets"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
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
        "comment":         (
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
            "description":         (
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

    ticket_type_id: Mapped[str] = mapped_column(GUID(), ForeignKey("ticket_types.id", ondelete="RESTRICT"), nullable=False)
    serial_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 1..N per type
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    holder_person_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="SET NULL"))
    qr_code: Mapped[Optional[str]] = mapped_column(sa.String(128))  # token/nonce
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=text("'issued'"))  # issued|checked_in|void
    issued_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    created_at, updated_at = ts_cols()

    order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        sa.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # relationships
    order: Mapped["Order"] = relationship("Order", back_populates="tickets", lazy="joined")

    ticket_type: Mapped[TicketType] = relationship(back_populates="tickets")