from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Student(UUIDMixin, Base):
    __tablename__ = "students"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | student_services_school_level | teaching_instructional_support; "
        "description=Stores students records for the application. "
        "References related entities via: person. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores students records for the application. "
            "References related entities via: person. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores students records for the application. "
            "References related entities via: person. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    person_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), sa.ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    person: Mapped["Person"] = relationship(
        "Person",
        back_populates="student",
        lazy="joined",
        passive_deletes=True,
    )

    student_number: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    graduation_year: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


