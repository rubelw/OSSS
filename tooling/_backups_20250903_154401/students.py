from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Student(UUIDMixin, Base):
    __tablename__ = "students"

    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), sa.ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    person: Mapped["Person"] = relationship(
        "Person",
        back_populates="student",
        lazy="joined",
        passive_deletes=True,
    )

    student_number: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    graduation_year: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
