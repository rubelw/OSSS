# src/OSSS/db/models/officials.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from .schools import School


class Official(UUIDMixin, Base):
    __tablename__ = "officials"

    school_id:     Mapped[str]        = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    name:          Mapped[str | None] = mapped_column(sa.String(255))
    certification: Mapped[str | None] = mapped_column(sa.String(128))
    phone:         Mapped[str | None] = mapped_column(sa.String(64))
    email:         Mapped[str | None] = mapped_column(sa.String(255), index=True)

    # relationships
    school: Mapped[School] = relationship("School")
