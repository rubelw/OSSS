from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
import uuid
from sqlalchemy.orm import relationship
from .base import Base, GUID


class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True, autoincrement=True)
    district_id = Column("district_id", GUID(), ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    school_code = Column("school_code", Text, unique=True)
    type = Column("type", Text)
    timezone = Column("timezone", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
