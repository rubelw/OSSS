from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class GradingPeriod(Base):
    __tablename__ = "grading_periods"
    id = Column(Integer, primary_key=True, autoincrement=True)
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    start_date = Column("start_date", Date, nullable=False)
    end_date = Column("end_date", Date, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
