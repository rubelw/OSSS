# src/OSSS/db/models/standards.py
from __future__ import annotations

from typing import Optional, List, ClassVar
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSON
from OSSS.db.models.associations import proposal_standard_map, unit_standard_map


class Standard(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "standards"
    __allow_unmapped__ = True  # keep NOTE out of mapper

    NOTE: ClassVar[str] = (
        "owner=curriculum_instruction_assessment; "
        "description=Stores standards records for the application. "
        "Key attributes include code. "
        "References related entities via: framework, parent. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "11 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores standards records for the application. "
            "Key attributes include code. "
            "References related entities via: framework, parent. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores standards records for the application. "
                "Key attributes include code. "
                "References related entities via: framework, parent. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "11 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    framework_id: Mapped[GUID] = mapped_column(
        GUID(),
        sa.ForeignKey("frameworks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)

    parent_id: Mapped[Optional[str]] = mapped_column(
        GUID(),
        sa.ForeignKey("standards.id", ondelete="SET NULL"),
        nullable=True,
    )
    grade_band: Mapped[Optional[str]] = mapped_column(sa.String(64))
    effective_from: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    effective_to: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    attributes = mapped_column(JSON, nullable=True)

    framework = relationship("Framework", back_populates="standards")

    parent: Mapped[Optional["Standard"]] = relationship(
        "Standard",
        remote_side="Standard.id",
        back_populates="children",
    )
    children: Mapped[List["Standard"]] = relationship(
        "Standard",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    # Many-to-many to curriculum units
    units: Mapped[List["CurriculumUnit"]] = relationship(
        "CurriculumUnit",
        secondary=unit_standard_map,
        back_populates="standards",
        lazy="selectin",
    )

    # Many-to-many to proposals
    proposals: Mapped[List["Proposal"]] = relationship(
        "Proposal",
        secondary=proposal_standard_map,
        back_populates="standards",
        lazy="selectin",
    )
