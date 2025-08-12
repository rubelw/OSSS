from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class MedicationAdministration(Base):
    __tablename__ = "medication_administrations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    medication_id = Column("medication_id", GUID(), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    administered_at = Column("administered_at", DateTime(timezone=True), nullable=False)
    dose = Column("dose", Text)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
