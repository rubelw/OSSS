from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Guardian(UUIDMixin, Base):
    __tablename__ = "guardians"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=student_services_school_level; "
        "description=Stores guardians records for the application. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "4 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores guardians records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "4 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores guardians records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "4 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    relationship: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


