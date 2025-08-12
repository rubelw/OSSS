from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class GradeScaleBand(Base):
    __tablename__ = "grade_scale_bands"
    id = Column(Integer, primary_key=True, autoincrement=True)
    grade_scale_id = Column("grade_scale_id", GUID(), ForeignKey("grade_scales.id", ondelete="CASCADE"), nullable=False)
    label = Column("label", Text, nullable=False)
    min_value = Column("min_value", Numeric(6,3), nullable=False)
    max_value = Column("max_value", Numeric(6,3), nullable=False)
    gpa_points = Column("gpa_points", Numeric(4,2))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
