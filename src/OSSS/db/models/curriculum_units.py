
from __future__ import annotations

from typing import Optional, List, Dict, Any, ClassVar
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .associations import unit_standard_map

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSON


class CurriculumUnit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "curriculum_units"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | teaching_instructional_support; "
        "description=Stores curriculum units records for the application. "
        "Key attributes include title. "
        "References related entities via: curriculum. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores curriculum units records for the application. "
            "Key attributes include title. "
            "References related entities via: curriculum. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores curriculum units records for the application. "
            "Key attributes include title. "
            "References related entities via: curriculum. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    curriculum_id: Mapped[str] = mapped_column(
        GUID(),
        sa.ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    curriculum: Mapped["Curriculum"] = relationship(
        "Curriculum", back_populates="units", lazy="joined",
        foreign_keys="CurriculumUnit.curriculum_id",
    )

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    metadata_json = mapped_column("metadata", JSON, nullable=True)

    standards: Mapped[List["Standard"]] = relationship(
        "Standard",
        secondary=unit_standard_map,
        back_populates="units",
        lazy="selectin",
    )
