from __future__ import annotations

from typing import Optional, List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, TimestampMixin


class GoverningBody(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "governing_bodies"

    org_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(sa.String(50))

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="governing_bodies",
        lazy="selectin",
    )

    # NEW: match Meeting.governing_body back_populates="meetings"
    meetings: Mapped[List["Meeting"]] = relationship(
        "Meeting",
        back_populates="governing_body",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

