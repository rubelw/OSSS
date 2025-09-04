# src/OSSS/db/models/scan_result.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class ScanResult(UUIDMixin, Base):
    __tablename__ = "scan_results"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores scan results records for the application. "
        "References related entities via: ticket. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores scan results records for the application. "
            "References related entities via: ticket. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores scan results records for the application. "
            "References related entities via: ticket. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    # Core fields
    ok: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    ticket_id: Mapped[Optional[str]] = mapped_column(
        GUID(), ForeignKey("tickets.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(),
        onupdate=sa.func.now(), nullable=False
    )

    # Relationships
    ticket: Mapped[Optional["Ticket"]] = relationship("Ticket")


