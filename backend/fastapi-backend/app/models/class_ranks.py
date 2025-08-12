from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from ._base import Base


class ClassRank(Base):
    __tablename__ = "class_ranks"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    school_id = Column("school_id", UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    term_id = Column("term_id", UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    rank = Column("rank", Integer, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    __table_args__ = (UniqueConstraint("school_id", "term_id", "student_id", name="uq_class_rank"), )
