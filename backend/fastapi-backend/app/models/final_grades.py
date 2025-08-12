from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class FinalGrade(Base):
    __tablename__ = "final_grades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    grading_period_id = Column("grading_period_id", GUID(), ForeignKey("grading_periods.id", ondelete="CASCADE"), nullable=False)
    numeric_grade = Column("numeric_grade", Numeric(6,3))
    letter_grade = Column("letter_grade", Text)
    credits_earned = Column("credits_earned", Numeric(5,2))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "section_id", "grading_period_id", name="uq_final_grade_period"), )
