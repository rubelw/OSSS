from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class PMPlan(UUIDMixin, Base):
    __tablename__ = "pm_plans"

    asset_id = sa.Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"))
    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"))
    name = sa.Column(sa.String(255), nullable=False)
    frequency = sa.Column(sa.String(64))
    next_due_at = sa.Column(sa.TIMESTAMP(timezone=True))
    last_completed_at = sa.Column(sa.TIMESTAMP(timezone=True))
    active = sa.Column(sa.Boolean, nullable=False, server_default=text("true"))
    procedure = sa.Column(JSONB, nullable=True)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="pm_plans")
    building = relationship("Building")
    generators = relationship("PMWorkGenerator", back_populates="plan", cascade="all, delete-orphan")
