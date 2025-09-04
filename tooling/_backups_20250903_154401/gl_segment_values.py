from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class GLSegmentValue(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gl_segment_values"

    segment_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.true())

    segment: Mapped["GLSegment"] = relationship("GLSegment", back_populates="values")
