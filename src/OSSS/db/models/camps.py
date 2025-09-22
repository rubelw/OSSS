# src/OSSS/db/models/camps.py
from __future__ import annotations

from datetime import date, datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID

# Use your shared mixin if available; otherwise provide a minimal fallback
try:
    from OSSS.db.mixins import TimestampMixin  # type: ignore
except Exception:
    class TimestampMixin:
        created_at: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)
        updated_at: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# If your School model lives in src/OSSS/db/models/school.py
from .schools import School


class Camp(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "camps"

    school_id:   Mapped[str]           = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    name:        Mapped[str | None]    = mapped_column(sa.String(255))
    description: Mapped[str | None]    = mapped_column(sa.Text)
    start_date:  Mapped[date | None]   = mapped_column(sa.Date)
    end_date:    Mapped[date | None]   = mapped_column(sa.Date)
    price_cents: Mapped[int | None]    = mapped_column(sa.Integer)
    capacity:    Mapped[int | None]    = mapped_column(sa.Integer)
    location:    Mapped[str | None]    = mapped_column(sa.String(255))

    # relationships
    school: Mapped[School] = relationship("School")
