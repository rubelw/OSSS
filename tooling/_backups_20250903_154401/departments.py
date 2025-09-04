from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Department(UUIDMixin, Base):
    __tablename__ = "departments"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


    # Link rows (delete-orphan here lets you remove links via ORM on the Department side)
    position_links: Mapped[list["DepartmentPositionIndex"]] = relationship(
        "DepartmentPositionIndex",
        back_populates="department",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Convenience: access positions directly (no secondary writes; uses association proxy)
    positions = association_proxy("position_links", "position")


