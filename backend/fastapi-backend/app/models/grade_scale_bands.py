from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class GradeScaleBand(Base):
    __tablename__ = "grade_scale_bands"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    grade_scale_id = Column("grade_scale_id", UUID(as_uuid=True), ForeignKey("grade_scales.id", ondelete="CASCADE"), nullable=False)
    label = Column("label", Text, nullable=False)
    min_value = Column("min_value", Numeric(6,3), nullable=False)
    max_value = Column("max_value", Numeric(6,3), nullable=False)
    gpa_points = Column("gpa_points", Numeric(4,2))
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
