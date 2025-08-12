from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class IepPlan(Base):
    __tablename__ = "iep_plans"
    id = Column(Integer, primary_key=True, autoincrement=True)
    special_ed_case_id = Column("special_ed_case_id", GUID(), ForeignKey("special_education_cases.id", ondelete="CASCADE"), nullable=False)
    effective_start = Column("effective_start", Date, nullable=False)
    effective_end = Column("effective_end", Date)
    summary = Column("summary", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
