from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class AssignmentCategory(Base):
    __tablename__ = "assignment_categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    weight = Column("weight", Numeric(5,2))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
