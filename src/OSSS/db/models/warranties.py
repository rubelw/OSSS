from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Warranty(UUIDMixin, Base):
    __tablename__ = "warranties"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=business_accounting; "
        "description=Stores warranties records for the application. "
        "References related entities via: asset, vendor. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores warranties records for the application. "
            "References related entities via: asset, vendor. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores warranties records for the application. "
            "References related entities via: asset, vendor. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    asset_id = sa.Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    vendor_id = sa.Column(GUID(), ForeignKey("vendors.id", ondelete="SET NULL"))
    policy_no = sa.Column(sa.String(128))
    start_date = sa.Column(sa.Date)
    end_date = sa.Column(sa.Date)
    terms = sa.Column(sa.Text)
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="warranties")
    vendor = relationship("Vendor", back_populates="warranties")


