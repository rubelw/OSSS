from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class WorkOrderTask(UUIDMixin, Base):
    __tablename__ = "work_order_tasks"

    work_order_id = sa.Column(GUID(), ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    seq = sa.Column(sa.Integer, nullable=False, server_default=text("1"))
    title = sa.Column(sa.String(255), nullable=False)
    is_mandatory = sa.Column(sa.Boolean, nullable=False, server_default=text("false"))
    status = sa.Column(sa.String(32))
    completed_at = sa.Column(sa.TIMESTAMP(timezone=True))
    notes = sa.Column(sa.Text)
    created_at, updated_at = ts_cols()

    work_order = relationship("WorkOrder", back_populates="tasks")
