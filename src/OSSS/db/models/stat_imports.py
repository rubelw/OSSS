# src/OSSS/db/models/stat_imports.py
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from .games import Game   # <-- add this

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB


class StatImport(UUIDMixin, Base):
    __tablename__ = "stat_imports"

    game_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("games.id", ondelete="SET NULL"))
    source_system: Mapped[str] = mapped_column(sa.String, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)
    file_uri: Mapped[str | None] = mapped_column(sa.String)
    status: Mapped[str | None] = mapped_column(sa.String)  # success, failed
    summary: Mapped[dict | None] = mapped_column(JSONB())

    # Relationship: keep the type non-optional (relationship objects are always present),
    # nullability is modeled by the FK above.
    game: Mapped[Optional["Game"]] = relationship()
