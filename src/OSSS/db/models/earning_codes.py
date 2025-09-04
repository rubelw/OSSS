from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EarningCode(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "earning_codes"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_finance; "
        "description=Stores earning codes records for the application. "
        "Key attributes include code, name. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores earning codes records for the application. "
            "Key attributes include code, name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores earning codes records for the application. "
            "Key attributes include code, name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)  # REG, OT, etc.
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    taxable: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.true())
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())


