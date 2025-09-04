from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class CICResolution(UUIDMixin, Base):
    __tablename__ = "cic_resolutions"

    meeting_id     = sa.Column(GUID(), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    title          = sa.Column(sa.Text, nullable=False)
    summary        = sa.Column(sa.Text)
    effective_date = sa.Column(sa.Date)
    status         = sa.Column(sa.Text)  # adopted|rejected|tabled

    created_at, updated_at = ts_cols()

    meeting = relationship("CICMeeting", back_populates="resolutions")
