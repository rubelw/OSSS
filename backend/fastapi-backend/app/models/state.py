from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base  # ✅ correct Base import

class State(Base):
    __tablename__ = "states"

    # Keep these in sync with your Alembic migration
    code: Mapped[str] = mapped_column(sa.String(2), primary_key=True)  # e.g., "IA"
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False, unique=True)