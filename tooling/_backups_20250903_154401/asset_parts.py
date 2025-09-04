# OSSS/db/models/asset_part.py
from __future__ import annotations
from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import relationship
from OSSS.db.base import Base, GUID
from ._helpers import ts_cols

class AssetPart(Base):
    __tablename__ = "asset_parts"

    id = sa.Column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    asset_id = sa.Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    part_id  = sa.Column(GUID(), ForeignKey("parts.id",  ondelete="CASCADE"), nullable=False, index=True)

    qty = sa.Column(sa.Numeric(12, 2), nullable=False, server_default=text("1"))

    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="parts")
    part  = relationship("Part",  back_populates="asset_parts")

        sa.UniqueConstraint("asset_id", "part_id", name="uq_asset_parts_pair"),
        sa.CheckConstraint("qty > 0", name="ck_asset_parts_qty_positive"),
    )
