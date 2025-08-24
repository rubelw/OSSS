from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class SpaceReservation(UUIDMixin, Base):
    __tablename__ = "space_reservations"

    space_id = sa.Column(GUID(), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    booked_by_user_id = sa.Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    start_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False)
    end_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False)
    purpose = sa.Column(sa.String(255))
    status = sa.Column(sa.String(32), nullable=False, server_default=text("'booked'"))
    setup = sa.Column(JSONB, nullable=True)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    space = relationship("Space")
