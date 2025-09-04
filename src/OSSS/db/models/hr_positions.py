from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class HRPosition(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "hr_positions"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=hr_operations_talent; "
        "description=Stores hr positions records for the application. "
        "Key attributes include title. "
        "References related entities via: department segment. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores hr positions records for the application. "
            "Key attributes include title. "
            "References related entities via: department segment. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores hr positions records for the application. "
            "Key attributes include title. "
            "References related entities via: department segment. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    department_segment_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="SET NULL"))
    grade: Mapped[Optional[str]] = mapped_column(sa.String(32))
    fte: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 2))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    assignments: Mapped[list["HRPositionAssignment"]] = relationship(
        "HRPositionAssignment", back_populates="position", cascade="all, delete-orphan"
    )

    # Link rows
    department_links: Mapped[list["DepartmentPositionIndex"]] = relationship(
        "DepartmentPositionIndex",
        back_populates="position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Convenience: access departments directly
    departments = association_proxy("department_links", "department")

