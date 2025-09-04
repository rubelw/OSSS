from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class PartLocation(UUIDMixin, Base):
    __tablename__ = "part_locations"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=facilities_maintenance; "
        "description=Stores part locations records for the application. "
        "References related entities via: building, part, space. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "3 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores part locations records for the application. "
            "References related entities via: building, part, space. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores part locations records for the application. "
            "References related entities via: building, part, space. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        },
    }


    part_id = sa.Column(GUID(), ForeignKey("parts.id", ondelete="CASCADE"), nullable=False)
    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    space_id = sa.Column(GUID(), ForeignKey("spaces.id", ondelete="SET NULL"))
    location_code = sa.Column(sa.String(128))
    qty_on_hand = sa.Column(sa.Numeric(12, 2), nullable=False, server_default=text("0"))
    min_qty = sa.Column(sa.Numeric(12, 2))
    max_qty = sa.Column(sa.Numeric(12, 2))
    created_at, updated_at = ts_cols()

    part = relationship("Part", back_populates="locations")
    building = relationship("Building")
    space = relationship("Space")


