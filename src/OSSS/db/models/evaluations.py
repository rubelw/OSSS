# src/OSSS/db/models/evaluations.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, GUID, UUIDMixin, TimestampMixin, JSONB


# -------------------------------
# Templates & structure
# -------------------------------
class EvaluationTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_templates"

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    for_role: Mapped[Optional[str]] = mapped_column(sa.String(80))
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))

    sections: Mapped[list["EvaluationSection"]] = relationship(
        "EvaluationSection", back_populates="template", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["EvaluationAssignment"]] = relationship(
        "EvaluationAssignment", back_populates="template", cascade="all, delete-orphan"
    )


class EvaluationSection(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_sections"

    template_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_templates.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    order_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")

    template: Mapped["EvaluationTemplate"] = relationship("EvaluationTemplate", back_populates="sections")
    questions: Mapped[list["EvaluationQuestion"]] = relationship(
        "EvaluationQuestion", back_populates="section", cascade="all, delete-orphan"
    )


class EvaluationQuestion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_questions"

    section_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_sections.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    type: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # scale|text|multi
    scale_min: Mapped[Optional[int]] = mapped_column(sa.Integer)
    scale_max: Mapped[Optional[int]] = mapped_column(sa.Integer)
    weight: Mapped[Optional[float]] = mapped_column(sa.Float)

    section: Mapped["EvaluationSection"] = relationship("EvaluationSection", back_populates="questions")


# -------------------------------
# Cycle & assignments
# -------------------------------
class EvaluationCycle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_cycles"

    org_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    start_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    end_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    assignments: Mapped[list["EvaluationAssignment"]] = relationship(
        "EvaluationAssignment", back_populates="cycle", cascade="all, delete-orphan"
    )
    reports: Mapped[list["EvaluationReport"]] = relationship(
        "EvaluationReport", back_populates="cycle", cascade="all, delete-orphan"
    )


class EvaluationAssignment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_assignments"

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


# -------------------------------
# Responses & sign-off
# -------------------------------
class EvaluationResponse(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_responses"

    assignment_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False
    )
    value_num: Mapped[Optional[float]] = mapped_column(sa.Float)
    value_text: Mapped[Optional[str]] = mapped_column(sa.Text)
    comment: Mapped[Optional[str]] = mapped_column(sa.Text)
    answered_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    assignment: Mapped["EvaluationAssignment"] = relationship("EvaluationAssignment", back_populates="responses")
    question: Mapped["EvaluationQuestion"] = relationship("EvaluationQuestion")


class EvaluationSignoff(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_signoffs"

    assignment_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False
    )
    signer_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("users.id"), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(sa.Text)

    assignment: Mapped["EvaluationAssignment"] = relationship("EvaluationAssignment", back_populates="signoffs")


class EvaluationFile(Base):
    __tablename__ = "evaluation_files"

    assignment_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)


class EvaluationReport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_reports"

    cycle_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[Optional[dict]] = mapped_column(JSONB())
    generated_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    file_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("files.id", ondelete="SET NULL"))

    cycle: Mapped["EvaluationCycle"] = relationship("EvaluationCycle", back_populates="reports")
