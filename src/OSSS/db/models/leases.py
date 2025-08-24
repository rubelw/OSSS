from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Lease(UUIDMixin, Base):
    __tablename__ = "leases"

    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    landlord = sa.Column(sa.String(255))
    tenant = sa.Column(sa.String(255))
    start_date = sa.Column(sa.Date)
    end_date = sa.Column(sa.Date)
    base_rent = sa.Column(sa.Numeric(14, 2))
    rent_schedule = sa.Column(JSONB, nullable=True)
    options = sa.Column(JSONB, nullable=True)
    documents = sa.Column(JSONB, nullable=True)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    building = relationship("Building")
