from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Facility(UUIDMixin, Base):
    __tablename__ = "facilities"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_operations; "
        "description=Stores facilities records for the application. "
        "Key attributes include name, code. "
        "References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores facilities records for the application. "
            "Key attributes include name, code. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores facilities records for the application. "
            "Key attributes include name, code. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    school_id = sa.Column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = sa.Column(sa.String(255), nullable=False)
    code = sa.Column(sa.String(64), unique=True)
    address = sa.Column(sa.JSON, nullable=True)
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    buildings = relationship("Building", back_populates="facility", cascade="all, delete-orphan")


