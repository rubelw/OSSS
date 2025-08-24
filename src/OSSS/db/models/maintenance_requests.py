from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class MaintenanceRequest(UUIDMixin, Base):
    __tablename__ = "maintenance_requests"

    school_id  = sa.Column(GUID(), ForeignKey("schools.id",   ondelete="SET NULL"))
    building_id= sa.Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    space_id   = sa.Column(GUID(), ForeignKey("spaces.id",    ondelete="SET NULL"))
    asset_id   = sa.Column(GUID(), ForeignKey("assets.id",    ondelete="SET NULL"))
    submitted_by_user_id = sa.Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    status = sa.Column(sa.String(32), nullable=False, server_default=text("'new'"))
    priority = sa.Column(sa.String(16))
    summary = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text)

    # legacy pointer (kept for compatibility)
    converted_work_order_id = sa.Column(GUID(), ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True)

    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    # canonical 1:1 link via WorkOrder.request_id
    work_order: Mapped[Optional["WorkOrder"]] = relationship(
        "WorkOrder",
        primaryjoin="MaintenanceRequest.id == foreign(WorkOrder.request_id)",
        back_populates="request",
        uselist=False,
    )

    # read-only convenience to legacy column
    converted_work_order: Mapped[Optional["WorkOrder"]] = relationship(
        "WorkOrder",
        primaryjoin="MaintenanceRequest.converted_work_order_id == WorkOrder.id",
        viewonly=True,
        uselist=False,
    )
