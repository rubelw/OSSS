from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class TestResult(Base):
    __tablename__ = "test_results"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    administration_id = Column("administration_id", UUID(as_uuid=True), ForeignKey("test_administrations.id", ondelete="CASCADE"), nullable=False)
    student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    scale_score = Column("scale_score", Numeric(8,2))
    percentile = Column("percentile", Numeric(5,2))
    performance_level = Column("performance_level", Text)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    __table_args__ = (UniqueConstraint("administration_id", "student_id", name="uq_test_result_student"), )
