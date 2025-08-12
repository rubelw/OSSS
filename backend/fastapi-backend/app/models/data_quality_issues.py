from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column("entity_type", Text, nullable=False)
    entity_id = Column("entity_id", GUID(), nullable=False)
    rule = Column("rule", Text, nullable=False)
    severity = Column("severity", Text, nullable=False)
    details = Column("details", Text)
    detected_at = Column("detected_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
