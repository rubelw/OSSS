from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class TicketScan(UUIDMixin, Base):
    __tablename__ = "ticket_scans"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores ticket scans records for the application. "
        "References related entities via: scanned by user, ticket. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores ticket scans records for the application. "
            "References related entities via: scanned by user, ticket. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores ticket scans records for the application. "
            "References related entities via: scanned by user, ticket. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    ticket_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    scanned_by_user_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    scanned_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False)
    result: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # ok|duplicate|invalid|void
    location: Mapped[Optional[str]] = mapped_column(sa.String(255))
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at, updated_at = ts_cols()


