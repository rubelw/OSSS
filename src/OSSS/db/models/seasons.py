from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, UUIDMixin

class Season(UUIDMixin, Base):
    __tablename__ = "seasons"

    name: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # e.g. "2025-2026"
    start_year: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    end_year: Mapped[int] = mapped_column(sa.Integer, nullable=False)
