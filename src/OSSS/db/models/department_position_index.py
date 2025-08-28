# OSSS/db/models/department_position_index.py
from __future__ import annotations
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Index
from OSSS.db.base import Base, GUID

class DepartmentPositionIndex(Base):
    __tablename__ = "department_position_index"

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

    __table_args__ = (
        sa.UniqueConstraint("department_id", "position_id", name="uq_deptpos_pair"),
        Index("ix_deptpos_department_id", "department_id"),
        Index("ix_deptpos_position_id", "position_id"),
    )

    def __repr__(self) -> str:
        return f"<DepartmentPositionIndex id={self.id} dept={self.department_id} pos={self.position_id}>"
