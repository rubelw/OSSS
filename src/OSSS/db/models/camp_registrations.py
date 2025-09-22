# src/OSSS/db/models/camp_registrations.py
from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID

# Use your shared mixin if available; otherwise provide a minimal fallback
try:
    from OSSS.db.mixins import TimestampMixin  # type: ignore
except Exception:
    class TimestampMixin:
        created_at: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)
        updated_at: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

from .camps import Camp
from .common_enums import OrderStatus


class CampRegistration(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "camp_registrations"

    camp_id: Mapped[int] = mapped_column(ForeignKey("camps.id", ondelete="CASCADE"))
    camp: Mapped["Camp"] = relationship("Camp", back_populates="registrations")
    participant_name:    Mapped[str | None]     = mapped_column(sa.String(255))
    participant_grade:   Mapped[str | None]     = mapped_column(sa.String(64))
    guardian_contact:    Mapped[str | None]     = mapped_column(sa.String(255))
    paid_amount_cents:   Mapped[int | None]     = mapped_column(sa.Integer)
    status:              Mapped[OrderStatus]    = mapped_column(sa.Enum(OrderStatus, name="order_status", native_enum=False), nullable=False, default=OrderStatus.pending)
    registered_at:       Mapped[datetime]       = mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)

    # relationships
    camp: Mapped[Camp] = relationship("Camp", back_populates="registrations")
