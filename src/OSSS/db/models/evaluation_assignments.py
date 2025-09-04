from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationAssignment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_assignments"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | teaching_instructional_support; "
        "description=Stores evaluation assignments records for the application. "
        "References related entities via: cycle, evaluator user, subject user, template. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "4 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores evaluation assignments records for the application. "
            "References related entities via: cycle, evaluator user, subject user, template. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "4 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores evaluation assignments records for the application. "
            "References related entities via: cycle, evaluator user, subject user, template. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "4 foreign key field(s) detected."
        ),
        },
    }


    cycle_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False
    )
    subject_user_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("users.id"), nullable=False)
    evaluator_user_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("users.id"), nullable=False)
    template_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_templates.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))

    cycle: Mapped["EvaluationCycle"] = relationship("EvaluationCycle", back_populates="assignments")
    template: Mapped["EvaluationTemplate"] = relationship("EvaluationTemplate", back_populates="assignments")
    responses: Mapped[list["EvaluationResponse"]] = relationship(
        "EvaluationResponse", back_populates="assignment", cascade="all, delete-orphan"
    )
    signoffs: Mapped[list["EvaluationSignoff"]] = relationship(
        "EvaluationSignoff", back_populates="assignment", cascade="all, delete-orphan"
    )


