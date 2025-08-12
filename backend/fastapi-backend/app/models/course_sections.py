from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class CourseSection(Base):
    __tablename__ = "course_sections"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    course_id = Column("course_id", UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    term_id = Column("term_id", UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    section_number = Column("section_number", Text, nullable=False)
    capacity = Column("capacity", Integer)
    school_id = Column("school_id", UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    __table_args__ = (UniqueConstraint("course_id", "term_id", "section_number", name="uq_course_term_section"), )
