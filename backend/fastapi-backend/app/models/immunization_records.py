from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class ImmunizationRecord(Base):
    __tablename__ = "immunization_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    immunization_id = Column("immunization_id", GUID(), ForeignKey("immunizations.id", ondelete="CASCADE"), nullable=False)
    date_administered = Column("date_administered", Date, nullable=False)
    dose_number = Column("dose_number", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "immunization_id", "date_administered", name="uq_immunization_record"), )
