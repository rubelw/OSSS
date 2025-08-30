
from __future__ import annotations

from typing import Optional, List, Dict, Any
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSON


class CurriculumUnit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "curriculum_units"
    __table_args__ = (sa.UniqueConstraint("curriculum_id", "order_index", name="uq_unit_order"),)

    curriculum_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    metadata_json = mapped_column("metadata", JSON, nullable=True)

    curriculum = relationship("Curriculum", back_populates="units")
    standards: Mapped[List["UnitStandardMap"]] = relationship("UnitStandardMap", back_populates="unit", cascade="all, delete-orphan")
