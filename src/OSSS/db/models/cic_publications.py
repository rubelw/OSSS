from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class CICPublication(UUIDMixin, Base):
    __tablename__ = "cic_publications"

    meeting_id   = sa.Column(GUID(), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    published_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now())
    public_url   = sa.Column(sa.Text)
    is_final     = sa.Column(sa.Boolean, nullable=False, server_default=text("false"))

    created_at, updated_at = ts_cols()

    meeting = relationship("CICMeeting", back_populates="publications")
