from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Space(UUIDMixin, Base):
    __tablename__ = "spaces"
    __table_args__ = (UniqueConstraint("building_id", "code", name="uq_spaces_building_code"),)

    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    floor_id = sa.Column(GUID(), ForeignKey("floors.id", ondelete="SET NULL"), nullable=True)
    code = sa.Column(sa.String(64), nullable=False)  # room number
    name = sa.Column(sa.String(255))
    space_type = sa.Column(sa.String(64))
    area_sqft = sa.Column(sa.Numeric(12, 2))
    capacity = sa.Column(sa.Integer)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    building = relationship("Building", back_populates="spaces")
    floor = relationship("Floor", back_populates="spaces")
    assets = relationship("Asset", back_populates="space")
