from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin


class ConcessionStand(UUIDMixin, Base):
    __tablename__ = "concession_stands"

    name: Mapped[str] = mapped_column(sa.String, nullable=False, unique=True, index=True)
    location: Mapped[str | None] = mapped_column(sa.String)

    # A stand has many items
    items: Mapped[list["ConcessionItem"]] = relationship(
        "ConcessionItem",
        back_populates="stand",
        cascade="all, delete-orphan",
    )
