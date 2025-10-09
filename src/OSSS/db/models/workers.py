from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin

class Worker(UUIDMixin, Base):
    __tablename__ = "workers"

    # example columns (keep your real ones)
    first_name: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    last_name:  Mapped[str] = mapped_column(sa.String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.func.now())

    # inverse relationship — name must match what you used above
    assignments: Mapped[list["WorkAssignment"]] = relationship(
        "WorkAssignment",
        back_populates="worker",
        cascade="all, delete-orphan",
    )
