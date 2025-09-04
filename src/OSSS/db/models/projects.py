from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Project(UUIDMixin, Base):
    __tablename__ = "projects"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores projects records for the application. "
        "Key attributes include name. "
        "References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "12 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores projects records for the application. "
            "Key attributes include name. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores projects records for the application. "
            "Key attributes include name. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    school_id = sa.Column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    name = sa.Column(sa.String(255), nullable=False)
    project_type = sa.Column(sa.String(32))
    status = sa.Column(sa.String(32))
    start_date = sa.Column(sa.Date)
    end_date = sa.Column(sa.Date)
    budget = sa.Column(sa.Numeric(14, 2))
    description = sa.Column(sa.Text)
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")


