from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class GradebookEntry(Base):
    __tablename__ = "gradebook_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column("assignment_id", GUID(), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    score = Column("score", Numeric(8,3))
    submitted_at = Column("submitted_at", DateTime(timezone=True))
    late = Column("late", Boolean, nullable=False, server_default=text("false"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_gradebook_student_assignment"), )
