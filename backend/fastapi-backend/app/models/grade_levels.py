from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class GradeLevel(Base):
    __tablename__ = "grade_levels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    ordinal = Column("ordinal", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
