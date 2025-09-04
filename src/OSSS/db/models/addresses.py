from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class Address(UUIDMixin, Base):
    __tablename__ = "addresses"
    __allow_unmapped__ = True  # optional; ignores other non-mapped attrs

    NOTE: ClassVar[str] = (
        "owner=student_services_school_level; "
        "description=Stores addresses records for the application. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. Primary key is `id`."
    )

    __table_args__ = {
        "comment": (
            "Stores addresses records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. Primary key is `id`."
        ),
        "info": {
            # your DBML exporter reads this to emit the table-level Note
            "note": NOTE,
            # optional structured metadata for other tooling
            "owner": "student_services_school_level",
            "description": (
                "Stores addresses records for the application. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "9 column(s) defined. Primary key is `id`."
            ),
        },
    }

    line1: Mapped[str] = mapped_column(sa.Text, nullable=False)
    line2: Mapped[Optional[str]] = mapped_column(sa.Text)
    city: Mapped[str] = mapped_column(sa.Text, nullable=False)
    state: Mapped[Optional[str]] = mapped_column(sa.Text)
    postal_code: Mapped[Optional[str]] = mapped_column(sa.Text)
    country: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)



