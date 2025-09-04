
from __future__ import annotations

from typing import Optional, List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSON


class Standard(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "standards"
        sa.UniqueConstraint("framework_id", "code", name="uq_standards_framework_code"),
    )

    framework_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("frameworks.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("standards.id", ondelete="SET NULL"))
    grade_band: Mapped[Optional[str]] = mapped_column(sa.String(64))  # optional helper
    effective_from: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    effective_to: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    attributes = mapped_column(JSON, nullable=True)

    framework = relationship("Framework", back_populates="standards")
    parent: Mapped[Optional["Standard"]] = relationship(
        "Standard", remote_side="Standard.id", back_populates="children"
    )
    children: Mapped[List["Standard"]] = relationship(
        "Standard", back_populates="parent", cascade="all, delete-orphan"
    )
