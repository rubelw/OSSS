from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Vote(UUIDMixin, Base):
    __tablename__ = "votes"

    motion_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("motions.id", ondelete="CASCADE"), nullable=False
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(sa.String(16), nullable=False)

    motion: Mapped["Motion"] = relationship("Motion", lazy="joined")
