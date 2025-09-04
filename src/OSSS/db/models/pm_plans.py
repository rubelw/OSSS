from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class PMPlan(UUIDMixin, Base):
    __tablename__ = "pm_plans"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=facilities_maintenance; "
        "description=Stores pm plans records for the application. "
        "Key attributes include name. "
        "References related entities via: asset, building. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "12 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores pm plans records for the application. "
            "Key attributes include name. "
            "References related entities via: asset, building. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores pm plans records for the application. "
            "Key attributes include name. "
            "References related entities via: asset, building. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    asset_id = sa.Column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"))
    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"))
    name = sa.Column(sa.String(255), nullable=False)
    frequency = sa.Column(sa.String(64))
    next_due_at = sa.Column(sa.TIMESTAMP(timezone=True))
    last_completed_at = sa.Column(sa.TIMESTAMP(timezone=True))
    active = sa.Column(sa.Boolean, nullable=False, server_default=sa.sql.true())
    procedure = sa.Column(sa.JSON, nullable=True)
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    asset = relationship("Asset", back_populates="pm_plans")
    building = relationship("Building")
    generators = relationship("PMWorkGenerator", back_populates="plan", cascade="all, delete-orphan")


