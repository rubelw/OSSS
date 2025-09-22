# src/OSSS/db/models/concession_items.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class ConcessionItem(UUIDMixin, Base):
    __tablename__ = "concession_items"

    stand_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("concession_stands.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(sa.String(255))
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    inventory: Mapped[int | None] = mapped_column(sa.Integer)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))

    # relationships
    stand: Mapped["ConcessionStand"] = relationship("ConcessionStand", backref="items")
