from __future__ import annotations
from datetime import datetime, date

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, Float, ForeignKey, TIMESTAMP
from .base import Base, UUIDMixin, GUID, JSONB, TSVectorType
import uuid
import sqlalchemy as sa


class EvaluationTemplate(UUIDMixin, Base):
    __tablename__ = "evaluation_templates"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    for_role: Mapped[Optional[str]] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

class EvaluationSection(UUIDMixin, Base):
    __tablename__ = "evaluation_sections"
    template_id: Mapped[str] = mapped_column(GUID(), ForeignKey("evaluation_templates.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

class EvaluationQuestion(UUIDMixin, Base):
    __tablename__ = "evaluation_questions"
    section_id: Mapped[str] = mapped_column(GUID(), ForeignKey("evaluation_sections.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # scale|text|multi
    scale_min: Mapped[Optional[int]] = mapped_column(Integer)
    scale_max: Mapped[Optional[int]] = mapped_column(Integer)
    weight: Mapped[Optional[float]] = mapped_column(Float)

class EvaluationCycle(UUIDMixin, Base):
    __tablename__ = "evaluation_cycles"
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore
    end_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))    # type: ignore

class EvaluationAssignment(UUIDMixin, Base):
    __tablename__ = "evaluation_assignments"
    cycle_id: Mapped[str] = mapped_column(GUID(), ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False)
    subject_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    evaluator_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    template_id: Mapped[str] = mapped_column(GUID(), ForeignKey("evaluation_templates.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(32))

class EvaluationResponse(UUIDMixin, Base):
    __tablename__ = "evaluation_responses"
    assignment_id: Mapped[str] = mapped_column(GUID(), ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[str] = mapped_column(GUID(), ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False)
    value_num: Mapped[Optional[float]] = mapped_column(Float)
    value_text: Mapped[Optional[str]] = mapped_column(Text)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    answered_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore

class EvaluationSignoff(UUIDMixin, Base):
    __tablename__ = "evaluation_signoffs"
    assignment_id: Mapped[str] = mapped_column(GUID(), ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False)
    signer_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # type: ignore
    note: Mapped[Optional[str]] = mapped_column(Text)

class EvaluationFile(Base):
    __tablename__ = "evaluation_files"
    assignment_id: Mapped[str] = mapped_column(GUID(), ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), primary_key=True)
    file_id: Mapped[str] = mapped_column(GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)

class EvaluationReport(UUIDMixin, Base):
    __tablename__ = "evaluation_reports"
    cycle_id: Mapped[str] = mapped_column(GUID(), ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[Optional[dict]] = mapped_column(JSONB())
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # type: ignore
    file_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("files.id", ondelete="SET NULL"))
