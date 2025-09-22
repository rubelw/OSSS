# src/OSSS/db/models/teams.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID
from .common_enums import Level

class Team(UUIDMixin, Base):
    __tablename__ = "teams"

    school_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    sport_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("sports.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    name: Mapped[str | None] = mapped_column(sa.String(128))
    level: Mapped[Level | None] = mapped_column(
        Enum(Level, name="level", native_enum=False),
        default=Level.Varsity,
        nullable=True,
    )

    # relationships
    school: Mapped["School"] = relationship("School", back_populates="teams")
    sport:  Mapped["Sport"]  = relationship("Sport", back_populates="teams")
