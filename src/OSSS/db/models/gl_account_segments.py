from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class GLAccountSegment(UUIDMixin, TimestampMixin, Base):
    """Optional: store segment/value breakdown for a GL account."""
    __tablename__ = "gl_account_segments"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=business_accounting; "
        "description=Stores gl account segments records for the application. "
        "References related entities via: account, segment, value. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "3 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores gl account segments records for the application. "
            "References related entities via: account, segment, value. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores gl account segments records for the application. "
            "References related entities via: account, segment, value. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        },
    }


    segment_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="CASCADE"), nullable=False)
    value_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("gl_segment_values.id", ondelete="SET NULL"))