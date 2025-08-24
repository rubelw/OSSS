from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class GLAccountSegment(UUIDMixin, TimestampMixin, Base):
    """Optional: store segment/value breakdown for a GL account."""
    __tablename__ = "gl_account_segments"
    __table_args__ = (sa.UniqueConstraint("account_id", "segment_id", name="uq_account_segment_once"),)

    account_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_accounts.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="CASCADE"), nullable=False)
    value_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("gl_segment_values.id", ondelete="SET NULL"))
