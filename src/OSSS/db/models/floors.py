from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Floor(UUIDMixin, Base):
    __tablename__ = "floors"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=facilities_maintenance; "
        "description=Stores floors records for the application. "
        "Key attributes include name. "
        "References related entities via: building. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores floors records for the application. "
            "Key attributes include name. "
            "References related entities via: building. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores floors records for the application. "
            "Key attributes include name. "
            "References related entities via: building. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    building_id = sa.Column(GUID(), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    level_code = sa.Column(sa.String(32), nullable=False)  # e.g., B1, 1, 2
    name = sa.Column(sa.String(128))
    created_at, updated_at = ts_cols()

    building = relationship("Building", back_populates="floors")
    spaces = relationship("Space", back_populates="floor")


