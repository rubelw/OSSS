# src/OSSS/db/models/concession_stands.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class ConcessionStand(UUIDMixin, Base):
    __tablename__ = "concession_stands"

    school_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(sa.String(255))
    location: Mapped[str | None] = mapped_column(sa.String(255))
    active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )

    # relationships
    school: Mapped["School"] = relationship("School")
    # Reverse link to items is provided by ConcessionItem(backref="items")
    # If you prefer explicit back_populates, switch both sides accordingly.
