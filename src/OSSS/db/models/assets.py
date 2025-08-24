from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols
from .work_orders import WorkOrder  # type-only import

class Asset(UUIDMixin, Base):
    __tablename__ = "assets"

    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    space_id    = sa.Column(GUID(), ForeignKey("spaces.id",    ondelete="SET NULL"))
    parent_asset_id = sa.Column(GUID(), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)

    tag = sa.Column(sa.String(128), nullable=False, unique=True)
    serial_no = sa.Column(sa.String(128))
    manufacturer = sa.Column(sa.String(255))
    model = sa.Column(sa.String(255))
    category = sa.Column(sa.String(64))
    status = sa.Column(sa.String(32))
    install_date = sa.Column(sa.Date)
    warranty_expires_at = sa.Column(sa.Date)
    expected_life_months = sa.Column(sa.Integer)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    building = relationship("Building")
    space    = relationship("Space", back_populates="assets")

    # self-referential: parent/children
    parent: Mapped[Optional["Asset"]] = relationship(
        "Asset",
        remote_side=lambda: [Asset.id],
        back_populates="children",
        foreign_keys=lambda: [Asset.parent_asset_id],
    )
    children: Mapped[List["Asset"]] = relationship(
        "Asset",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [Asset.parent_asset_id],
    )

    parts              = relationship("AssetPart", back_populates="asset")
    meters             = relationship("Meter", back_populates="asset")
    pm_plans           = relationship("PMPlan", back_populates="asset")
    warranties         = relationship("Warranty", back_populates="asset")
    compliance_records = relationship("ComplianceRecord", back_populates="asset")
    work_orders        = relationship(
        "WorkOrder",
        back_populates="asset",
        foreign_keys=lambda: [WorkOrder.asset_id],
    )
