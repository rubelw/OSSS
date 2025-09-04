from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Space(UUIDMixin, Base):
    __tablename__ = "spaces"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=facilities_maintenance; "
        "description=Stores spaces records for the application. "
        "Key attributes include code, name. "
        "References related entities via: building, floor. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "11 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores spaces records for the application. "
            "Key attributes include code, name. "
            "References related entities via: building, floor. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores spaces records for the application. "
            "Key attributes include code, name. "
            "References related entities via: building, floor. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }

    floor_id = sa.Column(GUID(), ForeignKey("floors.id", ondelete="SET NULL"), nullable=True)
    code = sa.Column(sa.String(64), nullable=False)  # room number
    name = sa.Column(sa.String(255))
    space_type = sa.Column(sa.String(64))
    area_sqft = sa.Column(sa.Numeric(12, 2))
    capacity = sa.Column(sa.Integer)
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    building_id = sa.Column(
        GUID,
        sa.ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    building = sa.orm.relationship("Building", back_populates="spaces")
    floor = relationship("Floor", back_populates="spaces")
    assets = relationship("Asset", back_populates="space")