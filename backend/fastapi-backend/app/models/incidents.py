from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    occurred_at = Column("occurred_at", DateTime(timezone=True), nullable=False)
    behavior_code = Column("behavior_code", Text, ForeignKey("behavior_codes.code", ondelete="RESTRICT"), nullable=False)
    description = Column("description", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
