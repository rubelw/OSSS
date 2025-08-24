from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class Building(UUIDMixin, Base):
    __tablename__ = "buildings"

    facility_id = sa.Column(GUID(), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False)
    name = sa.Column(sa.String(255), nullable=False)
    code = sa.Column(sa.String(64), unique=True)
    year_built = sa.Column(sa.Integer)
    floors_count = sa.Column(sa.Integer)
    gross_sqft = sa.Column(sa.Numeric(12, 2))
    use_type = sa.Column(sa.String(64))
    address = sa.Column(JSONB, nullable=True)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    facility = relationship("Facility", back_populates="buildings")
    floors = relationship("Floor", back_populates="building", cascade="all, delete-orphan")
    spaces = relationship("Space", back_populates="building", cascade="all, delete-orphan")
