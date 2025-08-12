from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID, UUIDMixin


class AcademicTerm(UUIDMixin, Base):
    __tablename__ = "academic_terms"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    type = Column("type", Text)
    start_date = Column("start_date", Date, nullable=False)
    end_date = Column("end_date", Date, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
