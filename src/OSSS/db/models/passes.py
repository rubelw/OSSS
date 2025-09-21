# src/OSSS/db/models/passes.py
from __future__ import annotations
from datetime import date
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, GUID

class Pass(UUIDMixin, Base):
    __tablename__ = "passes"

    school_id:  Mapped[str] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    name:       Mapped[str | None] = mapped_column(sa.String(128))
    description:Mapped[str | None] = mapped_column(sa.Text)
    price_cents:Mapped[int | None] = mapped_column(sa.Integer)
    valid_from: Mapped[date | None] = mapped_column(sa.Date)
    valid_to:   Mapped[date | None] = mapped_column(sa.Date)
    max_uses:   Mapped[int | None] = mapped_column(sa.Integer)
