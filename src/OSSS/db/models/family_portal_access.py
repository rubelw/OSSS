# OSSS/db/models/family_portal_access.py
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID

class FamilyPortalAccess(Base):
    __tablename__ = "family_portal_access"

    id: Mapped[str] = mapped_column(
        GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )

    guardian_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permissions: Mapped[str | None] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("guardian_id", "student_id", name="uq_family_portal_access_pair"),
    )
