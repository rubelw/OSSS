from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class Building(UUIDMixin, Base):
    __tablename__ = "buildings"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=facilities_maintenance; "
        "description=Stores buildings records for the application. "
        "Key attributes include name, code. "
        "References related entities via: facility. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "12 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores buildings records for the application. "
            "Key attributes include name, code. "
            "References related entities via: facility. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores buildings records for the application. "
            "Key attributes include name, code. "
            "References related entities via: facility. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    facility_id = sa.Column(GUID(), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False)
    name = sa.Column(sa.String(255), nullable=False)
    code = sa.Column(sa.String(64), unique=True)
    year_built = sa.Column(sa.Integer)
    floors_count = sa.Column(sa.Integer)
    gross_sqft = sa.Column(sa.Numeric(12, 2))
    use_type = sa.Column(sa.String(64))
    address = sa.Column(sa.JSON, nullable=True)
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    facility = relationship("Facility", back_populates="buildings")
    floors = relationship("Floor", back_populates="building", cascade="all, delete-orphan")
    spaces = sa.orm.relationship(
        "Space",
        back_populates="building",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

