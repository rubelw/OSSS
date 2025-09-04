from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Part(UUIDMixin, Base):
    __tablename__ = "parts"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores parts records for the application. "
        "Key attributes include name. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores parts records for the application. "
            "Key attributes include name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores parts records for the application. "
            "Key attributes include name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    sku = sa.Column(sa.String(128), unique=True)
    name = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.Text)
    unit_cost = sa.Column(sa.Numeric(12, 2))
    uom = sa.Column(sa.String(32))
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    locations = relationship("PartLocation", back_populates="part")
    work_order_parts = relationship("WorkOrderPart", back_populates="part")
    asset_parts = relationship("AssetPart", back_populates="part")


