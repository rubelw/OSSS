from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class GLSegment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gl_segments"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_finance; "
        "description=Stores gl segments records for the application. "
        "Key attributes include code, name. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores gl segments records for the application. "
            "Key attributes include code, name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores gl segments records for the application. "
            "Key attributes include code, name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    seq: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    length: Mapped[Optional[int]] = mapped_column(sa.Integer)
    required: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.true())

    values: Mapped[List["GLSegmentValue"]] = relationship(
        "GLSegmentValue",
        back_populates="segment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

