from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class Assignment(Base):
    __tablename__ = "assignments"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    section_id = Column("section_id", UUID(as_uuid=True), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    category_id = Column("category_id", UUID(as_uuid=True), ForeignKey("assignment_categories.id", ondelete="SET NULL"))
    name = Column("name", Text, nullable=False)
    due_date = Column("due_date", Date)
    points_possible = Column("points_possible", Numeric(8,2))
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
