from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

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
