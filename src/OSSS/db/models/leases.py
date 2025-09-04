from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Lease(UUIDMixin, Base):
    __tablename__ = "leases"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=facilities_maintenance; "
        "description=Stores leases records for the application. "
        "References related entities via: building. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "13 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores leases records for the application. "
            "References related entities via: building. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "13 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores leases records for the application. "
            "References related entities via: building. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "13 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="SET NULL"))
    landlord = sa.Column(sa.String(255))
    tenant = sa.Column(sa.String(255))
    start_date = sa.Column(sa.Date)
    end_date = sa.Column(sa.Date)
    base_rent = sa.Column(sa.Numeric(14, 2))
    rent_schedule = sa.Column(sa.JSON, nullable=True)
    options = sa.Column(sa.JSON, nullable=True)
    documents = sa.Column(sa.JSON, nullable=True)
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    building = relationship("Building")


