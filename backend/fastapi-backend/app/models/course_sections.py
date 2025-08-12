from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class CourseSection(Base):
    __tablename__ = "course_sections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column("course_id", GUID(), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    section_number = Column("section_number", Text, nullable=False)
    capacity = Column("capacity", Integer)
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("course_id", "term_id", "section_number", name="uq_course_term_section"), )
