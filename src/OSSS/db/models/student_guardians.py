from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, GUID

class StudentGuardian(Base):
    __tablename__ = "student_guardians"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    student_id: Mapped[str] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    guardian_id: Mapped[str] = mapped_column(GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), nullable=False, index=True)

    custody: Mapped[str | None] = mapped_column(sa.Text)
    is_primary: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))
    contact_order: Mapped[int | None] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("student_id", "guardian_id", name="uq_student_guardians_pair"),
    )
