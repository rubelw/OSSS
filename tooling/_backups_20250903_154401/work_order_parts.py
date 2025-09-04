from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class WorkOrderPart(UUIDMixin, Base):
    __tablename__ = "work_order_parts"

    work_order_id = sa.Column(GUID(), ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    part_id = sa.Column(GUID(), ForeignKey("parts.id", ondelete="SET NULL"))
    qty = sa.Column(sa.Numeric(12, 2), nullable=False, server_default=text("1"))
    unit_cost = sa.Column(sa.Numeric(12, 2))
    extended_cost = sa.Column(sa.Numeric(12, 2))
    notes = sa.Column(sa.Text)
    created_at, updated_at = ts_cols()

    work_order = relationship("WorkOrder", back_populates="parts_used")
    part = relationship("Part", back_populates="work_order_parts")
