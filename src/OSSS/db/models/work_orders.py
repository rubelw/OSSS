from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class WorkOrder(UUIDMixin, Base):
    __tablename__ = "work_orders"

    school_id  = sa.Column(GUID(), ForeignKey("schools.id",   ondelete="SET NULL"))
    building_id= sa.Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    space_id   = sa.Column(GUID(), ForeignKey("spaces.id",    ondelete="SET NULL"))
    asset_id   = sa.Column(GUID(), ForeignKey("assets.id",    ondelete="SET NULL"))

    # canonical pointer back to request
    request_id = sa.Column(GUID(), ForeignKey("maintenance_requests.id", ondelete="SET NULL"),
                        unique=True, nullable=True)

    status = sa.Column(sa.String(32), nullable=False, server_default=text("'open'"))
    priority = sa.Column(sa.String(16))
    category = sa.Column(sa.String(64))
    summary = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text)
    requested_due_at   = sa.Column(sa.TIMESTAMP(timezone=True))
    scheduled_start_at = sa.Column(sa.TIMESTAMP(timezone=True))
    scheduled_end_at   = sa.Column(sa.TIMESTAMP(timezone=True))
    completed_at       = sa.Column(sa.TIMESTAMP(timezone=True))
    assigned_to_user_id= sa.Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    materials_cost = sa.Column(sa.Numeric(12, 2))
    labor_cost     = sa.Column(sa.Numeric(12, 2))
    other_cost     = sa.Column(sa.Numeric(12, 2))
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    request: Mapped[Optional["MaintenanceRequest"]] = relationship(
        "MaintenanceRequest",
        back_populates="work_order",
        foreign_keys=[request_id],
        uselist=False,
    )

    asset = relationship(
        "Asset",
        back_populates="work_orders",
        foreign_keys=[asset_id],
    )

    tasks      = relationship("WorkOrderTask", back_populates="work_order", cascade="all, delete-orphan")
    time_logs  = relationship("WorkOrderTimeLog", back_populates="work_order", cascade="all, delete-orphan")
    parts_used = relationship("WorkOrderPart",  back_populates="work_order", cascade="all, delete-orphan")

    # optional view of “converted from” via MR.converted_work_order_id (no back_populates)
    converted_from_request: Mapped[Optional["MaintenanceRequest"]] = relationship(
        "MaintenanceRequest",
        primaryjoin="WorkOrder.id == foreign(MaintenanceRequest.converted_work_order_id)",
        viewonly=True,
        uselist=False,
    )
