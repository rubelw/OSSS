# src/OSSS/db/models/store_products.py
from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID

# Reuse your common timestamp mixin if present; provide a minimal fallback for safety.
try:
    from OSSS.db.mixins import TimestampMixin  # type: ignore
except Exception:
    class TimestampMixin:
        created_at: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)
        updated_at: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

from .schools import School


class StoreProduct(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "store_products"

    school_id:    Mapped[str]         = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    sku:          Mapped[str | None]  = mapped_column(sa.String(128), unique=True)
    name:         Mapped[str | None]  = mapped_column(sa.String(255))
    description:  Mapped[str | None]  = mapped_column(sa.Text)
    price_cents:  Mapped[int]         = mapped_column(sa.Integer, nullable=False)
    inventory:    Mapped[int | None]  = mapped_column(sa.Integer)
    active:       Mapped[bool]        = mapped_column(sa.Boolean, default=True, nullable=False)

    # relationships
    school: Mapped[School] = relationship("School")
