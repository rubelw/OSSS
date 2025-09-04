from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class JournalBatch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "journal_batches"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_finance; "
        "description=Stores journal batches records for the application. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores journal batches records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores journal batches records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    batch_no: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255))
    source: Mapped[Optional[str]] = mapped_column(sa.String(64))         # subsystem/source tag
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'open'"))  # open, posted
    posted_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    entries: Mapped[List["JournalEntry"]] = relationship(
        "JournalEntry",
        back_populates="batch",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )



