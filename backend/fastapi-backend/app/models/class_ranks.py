from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class ClassRank(Base):
    __tablename__ = "class_ranks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    rank = Column("rank", Integer, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("school_id", "term_id", "student_id", name="uq_class_rank"), )
