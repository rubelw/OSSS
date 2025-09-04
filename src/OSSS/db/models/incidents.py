from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class Incident(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "incidents"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores incidents records for the application. "
        "References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores incidents records for the application. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores incidents records for the application. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    # nullable SET NULL to allow school deletion without removing incidents
    school_id: Mapped[Optional[str]] = mapped_column(
        GUID(), sa.ForeignKey("schools.id", ondelete="SET NULL")
    )

    occurred_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)

    # Behavior codes are stored in a lookup table; keep FK to its natural key
    behavior_code: Mapped[str] = mapped_column(
        sa.Text,
        sa.ForeignKey("behavior_codes.code", ondelete="RESTRICT"),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(sa.Text)
