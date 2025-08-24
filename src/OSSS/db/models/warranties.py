from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Warranty(UUIDMixin, Base):
    __tablename__ = "warranties"

    asset_id = sa.Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    vendor_id = sa.Column(GUID(), ForeignKey("vendors.id", ondelete="SET NULL"))
    policy_no = sa.Column(sa.String(128))
    start_date = sa.Column(sa.Date)
    end_date = sa.Column(sa.Date)
    terms = sa.Column(sa.Text)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="warranties")
    vendor = relationship("Vendor", back_populates="warranties")
