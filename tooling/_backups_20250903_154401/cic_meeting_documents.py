from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class CICMeetingDocument(UUIDMixin, Base):
    __tablename__ = "cic_meeting_documents"

    meeting_id  = sa.Column(GUID(), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    document_id = sa.Column(GUID(), ForeignKey("documents.id",    ondelete="SET NULL"))
    file_uri    = sa.Column(sa.Text)
    label       = sa.Column(sa.Text)

    created_at, updated_at = ts_cols()

    meeting = relationship("CICMeeting", back_populates="meeting_documents")
