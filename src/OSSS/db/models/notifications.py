from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores notifications records for the application. "
        "References related entities via: user. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores notifications records for the application. "
            "References related entities via: user. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores notifications records for the application. "
            "References related entities via: user. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    user_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB())
    read_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
