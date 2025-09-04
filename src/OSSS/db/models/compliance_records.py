from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class ComplianceRecord(UUIDMixin, Base):
    __tablename__ = "compliance_records"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=facilities_maintenance; "
        "description=Stores compliance records records for the application. "
        "References related entities via: asset, building. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "12 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores compliance records records for the application. "
            "References related entities via: asset, building. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores compliance records records for the application. "
            "References related entities via: asset, building. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    asset_id = sa.Column(GUID(), ForeignKey("assets.id", ondelete="SET NULL"))
    record_type = sa.Column(sa.String(64), nullable=False)
    authority = sa.Column(sa.String(255))
    identifier = sa.Column(sa.String(128))
    issued_at = sa.Column(sa.Date)
    expires_at = sa.Column(sa.Date)
    documents = sa.Column(sa.JSON, nullable=True)
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    building = relationship("Building")
    asset = relationship("Asset", back_populates="compliance_records")


