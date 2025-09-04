from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Floor(UUIDMixin, Base):
    __tablename__ = "floors"

    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    level_code = sa.Column(sa.String(32), nullable=False)  # e.g., B1, 1, 2
    name = sa.Column(sa.String(128))
    created_at, updated_at = ts_cols()

    building = relationship("Building", back_populates="floors")
    spaces = relationship("Space", back_populates="floor")
