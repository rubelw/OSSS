from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class Accommodation(Base):
    __tablename__ = "accommodations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    iep_plan_id = Column("iep_plan_id", GUID(), ForeignKey("iep_plans.id", ondelete="CASCADE"))
    applies_to = Column("applies_to", Text)
    description = Column("description", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
