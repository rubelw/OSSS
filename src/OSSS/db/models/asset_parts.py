from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class AssetPart(Base):
    __tablename__ = "asset_parts"

    asset_id = sa.Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    part_id = sa.Column(GUID(), ForeignKey("parts.id", ondelete="CASCADE"), primary_key=True)
    qty = sa.Column(sa.Numeric(12, 2), nullable=False, server_default=text("1"))
    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="parts")
    part = relationship("Part", back_populates="asset_parts")
