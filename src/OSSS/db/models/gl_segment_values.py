from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class GLSegmentValue(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gl_segment_values"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_finance; "
        "description=Stores gl segment values records for the application. "
        "Key attributes include code, name. "
        "References related entities via: segment. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores gl segment values records for the application. "
            "Key attributes include code, name. "
            "References related entities via: segment. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores gl segment values records for the application. "
            "Key attributes include code, name. "
            "References related entities via: segment. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.true())

    segment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        sa.ForeignKey("gl_segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    segment: Mapped["GLSegment"] = relationship(
        "GLSegment",
        back_populates="values",
        lazy="joined",
    )
