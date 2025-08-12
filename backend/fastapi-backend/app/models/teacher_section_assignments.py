from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class TeacherSectionAssignment(Base):
    __tablename__ = "teacher_section_assignments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    staff_id = Column("staff_id", GUID(), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    role = Column("role", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("staff_id", "section_id", name="uq_teacher_section"), )
