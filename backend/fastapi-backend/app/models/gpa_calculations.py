from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class GpaCalculation(Base):
    __tablename__ = "gpa_calculations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    gpa = Column("gpa", Numeric(4,3), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "term_id", name="uq_gpa_term"), )
