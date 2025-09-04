# OSSS/db/models/department_position_index.py
from __future__ import annotations
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Index
from OSSS.db.base import Base, GUID
from typing import ClassVar

class DepartmentPositionIndex(Base):
    __tablename__ = "department_position_index"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=hr_operations_talent; "
        "description=Stores department position index records for the application. "
        "References related entities via: department, position. "
        "Includes standard audit timestamps (created_at). "
        "4 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores department position index records for the application. "
            "References related entities via: department, position. "
            "Includes standard audit timestamps (created_at). "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores department position index records for the application. "
            "References related entities via: department, position. "
            "Includes standard audit timestamps (created_at). "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("hr_positions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    department: Mapped["Department"] = relationship(
        "Department", back_populates="position_links", passive_deletes=True
    )
    position: Mapped["HRPosition"] = relationship(
        "HRPosition", back_populates="department_links", passive_deletes=True
    )
