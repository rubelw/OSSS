from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import ClassVar

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Publication(UUIDMixin, Base):
    __tablename__ = "publications"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment; "
        "description=Stores cic publications records for the application. "
        "References related entities via: meeting. "
        "Includes standard audit timestamps (published_at, created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores cic publications records for the application. "
            "References related entities via: meeting. "
            "Includes standard audit timestamps (published_at, created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores cic publications records for the application. "
            "References related entities via: meeting. "
            "Includes standard audit timestamps (published_at, created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    meeting_id   = sa.Column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    published_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now())
    public_url   = sa.Column(sa.Text)
    is_final     = sa.Column(sa.Text, nullable=False, server_default=text("0"))

    created_at, updated_at = ts_cols()

    meeting = relationship("Meeting", back_populates="publications")


