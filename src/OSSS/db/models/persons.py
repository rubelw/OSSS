from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from OSSS.db.models.enums import Gender  # 👈 NEW

class Person(UUIDMixin, Base):
    __tablename__ = "persons"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=division_of_technology_data; "
        "description=Stores persons records for the application. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment": (
            "Stores persons records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores persons records for the application. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "10 column(s) defined. "
                "Primary key is `id`."
            ),
        },
    }

    first_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    last_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(sa.Text)
    dob: Mapped[Optional[date]] = mapped_column(sa.Date)
    email: Mapped[Optional[str]] = mapped_column(sa.Text)
    phone: Mapped[Optional[str]] = mapped_column(sa.Text)

    # 👇 UPDATED: use Gender enum instead of plain Text
    gender: Mapped[Optional[Gender]] = mapped_column(
        sa.Enum(Gender, name="gender"),  # PG enum name "gender"
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    student: Mapped[Optional["Student"]] = relationship(
        "Student",
        back_populates="person",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
