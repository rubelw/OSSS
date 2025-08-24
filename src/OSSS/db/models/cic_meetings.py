from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class CICMeeting(UUIDMixin, Base):
    __tablename__ = "cic_meetings"

    committee_id = sa.Column(GUID(), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    title        = sa.Column(sa.Text, nullable=False)
    scheduled_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False)
    ends_at      = sa.Column(sa.TIMESTAMP(timezone=True))
    location     = sa.Column(sa.Text)
    status       = sa.Column(sa.Text, nullable=False, server_default=text("'scheduled'"))
    is_public    = sa.Column(sa.Boolean, nullable=False, server_default=text("true"))

    created_at, updated_at = ts_cols()

    committee      = relationship("CICCommittee", back_populates="meetings")
    agenda_items   = relationship("CICAgendaItem",     back_populates="meeting",   cascade="all, delete-orphan")
    resolutions    = relationship("CICResolution",     back_populates="meeting",   cascade="all, delete-orphan")
    publications   = relationship("CICPublication",    back_populates="meeting",   cascade="all, delete-orphan")
    meeting_documents = relationship("CICMeetingDocument", back_populates="meeting", cascade="all, delete-orphan")
