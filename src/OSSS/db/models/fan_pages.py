# src/OSSS/db/models/fan_pages.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols
from .schools import School


class FanPage(UUIDMixin, Base):
    __tablename__ = "fan_pages"

    school_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        sa.String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(sa.String(255))
    content_md: Mapped[str | None] = mapped_column(sa.Text)
    published: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
    )

    # standard audit timestamps
    created_at, updated_at = ts_cols()

    # relationships
    school: Mapped[School] = relationship("School")
