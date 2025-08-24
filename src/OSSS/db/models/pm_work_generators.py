from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class PMWorkGenerator(UUIDMixin, Base):
    __tablename__ = "pm_work_generators"

    pm_plan_id = sa.Column(GUID(), ForeignKey("pm_plans.id", ondelete="CASCADE"), nullable=False)
    last_generated_at = sa.Column(sa.TIMESTAMP(timezone=True))
    lookahead_days = sa.Column(sa.Integer)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    plan = relationship("PMPlan", back_populates="generators")
