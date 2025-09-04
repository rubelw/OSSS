from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class Webhook(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "webhooks"

    target_url: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(sa.String(255))
    # Store as JSON for ORM simplicity; keep ARRAY in DB via migrations if desired.
    events: Mapped[Optional[list[str]]] = mapped_column(JSONB())
