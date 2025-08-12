from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class FinalGrade(Base):
    __tablename__ = "final_grades"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id = Column("section_id", UUID(as_uuid=True), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    grading_period_id = Column("grading_period_id", UUID(as_uuid=True), ForeignKey("grading_periods.id", ondelete="CASCADE"), nullable=False)
    numeric_grade = Column("numeric_grade", Numeric(6,3))
    letter_grade = Column("letter_grade", Text)
    credits_earned = Column("credits_earned", Numeric(5,2))
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "section_id", "grading_period_id", name="uq_final_grade_period"), )
