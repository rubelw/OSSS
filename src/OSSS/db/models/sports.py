# src/OSSS/db/models/sports.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID
from .schools import School

class Sport(UUIDMixin, Base):
    __tablename__ = "sports"
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)

    teams: Mapped[list["Team"]] = relationship("Team", back_populates="sport", cascade="all, delete-orphan")
