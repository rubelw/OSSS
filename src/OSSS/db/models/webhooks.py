from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class Webhook(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "webhooks"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores webhooks records for the application. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores webhooks records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores webhooks records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    target_url: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(sa.String(255))
    # Store as JSON for ORM simplicity; keep ARRAY in DB via migrations if desired.
    events: Mapped[Optional[list[str]]] = mapped_column(JSONB())


