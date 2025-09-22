# src/OSSS/db/models/fan_app_settings.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols
from .schools import School


class FanAppSetting(UUIDMixin, Base):
    __tablename__ = "fan_app_settings"

    school_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("schools.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    theme: Mapped[dict | None] = mapped_column(JSONB())
    features: Mapped[dict | None] = mapped_column(JSONB())

    # standard audit timestamps
    created_at, updated_at = ts_cols()

    # relationships
    school: Mapped[School] = relationship("School")
