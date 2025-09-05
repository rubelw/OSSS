# OSSS/db/models/asset_part.py
from __future__ import annotations
from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, func, text
from sqlalchemy.orm import relationship
from OSSS.db.base import Base, GUID
from ._helpers import ts_cols
from typing import ClassVar

class AssetPart(Base):
    __tablename__ = "asset_parts"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_operations; "
        "description=Stores asset parts records for the application. "
        "References related entities via: asset, part. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores asset parts records for the application. "
            "References related entities via: asset, part. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores asset parts records for the application. "
            "References related entities via: asset, part. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id = sa.Column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    asset_id = sa.Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    part_id  = sa.Column(GUID(), ForeignKey("parts.id",  ondelete="CASCADE"), nullable=False, index=True)

    qty = sa.Column(sa.Numeric(12, 2), nullable=False, server_default=text("1"))

    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="parts")
    part  = relationship("Part",  back_populates="asset_parts")
