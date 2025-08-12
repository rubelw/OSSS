from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class TranscriptLine(Base):
    __tablename__ = "transcript_lines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id = Column("course_id", GUID(), ForeignKey("courses.id", ondelete="SET NULL"))
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="SET NULL"))
    credits_attempted = Column("credits_attempted", Numeric(5,2))
    credits_earned = Column("credits_earned", Numeric(5,2))
    final_letter = Column("final_letter", Text)
    final_numeric = Column("final_numeric", Numeric(6,3))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
