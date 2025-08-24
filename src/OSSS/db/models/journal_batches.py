from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class JournalBatch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "journal_batches"

    batch_no: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255))
    source: Mapped[Optional[str]] = mapped_column(sa.String(64))         # subsystem/source tag
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'open'"))  # open, posted
    posted_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
