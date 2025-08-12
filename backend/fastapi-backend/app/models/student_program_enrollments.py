from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class StudentProgramEnrollment(Base):
    __tablename__ = "student_program_enrollments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    program_name = Column("program_name", Text, nullable=False)
    start_date = Column("start_date", Date, nullable=False)
    end_date = Column("end_date", Date)
    status = Column("status", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
