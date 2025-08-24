from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin


class Body(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bodies"

    org_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(sa.String(50))

    organization: Mapped[Organization] = relationship("Organization", back_populates="bodies")

    __table_args__ = (sa.Index("ix_bodies_org", "org_id"),)
