from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"
    course_id = Column("course_id", GUID(), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    prereq_course_id = Column("prereq_course_id", GUID(), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
