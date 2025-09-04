
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class UnitStandardMap(UUIDMixin, Base):
    __tablename__ = "unit_standard_map"

    unit_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("curriculum_units.id", ondelete="CASCADE"), nullable=False, index=True)
    standard_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True)

    unit = relationship("CurriculumUnit", back_populates="standards")
    standard = relationship("Standard")
