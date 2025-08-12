from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    entity_type = Column("entity_type", Text, nullable=False)
    entity_id = Column("entity_id", UUID(as_uuid=True), nullable=False)
    rule = Column("rule", Text, nullable=False)
    severity = Column("severity", Text, nullable=False)
    details = Column("details", Text)
    detected_at = Column("detected_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
