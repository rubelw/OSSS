from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class Accommodation(Base):
    __tablename__ = "accommodations"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    iep_plan_id = Column("iep_plan_id", UUID(as_uuid=True), ForeignKey("iep_plans.id", ondelete="CASCADE"))
    applies_to = Column("applies_to", Text)
    description = Column("description", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
