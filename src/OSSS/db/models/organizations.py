from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores organizations records for the application. "
        "Key attributes include name, code. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores organizations records for the application. "
            "Key attributes include name, code. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores organizations records for the application. "
            "Key attributes include name, code. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    name: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)

    # Renamed: bodies -> governing_bodies
    governing_bodies: Mapped[List["GoverningBody"]] = relationship(
        "GoverningBody",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Optional: temporary backwards-compat alias (read-only) to avoid breaking callers.
    # Remove once all references are migrated off `.bodies`.
    @property
    def bodies(self) -> List["GoverningBody"]:
        return self.governing_bodies

    # Keep existing curricula relationship as-is
    curricula: Mapped[List["Curriculum"]] = relationship(
        "Curriculum",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


