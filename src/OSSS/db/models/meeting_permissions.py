from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class MeetingPermission(Base):
    __tablename__ = "meeting_permissions"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    principal_type: Mapped[str] = mapped_column(sa.String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    permission: Mapped[str] = mapped_column(sa.String(50), primary_key=True)
