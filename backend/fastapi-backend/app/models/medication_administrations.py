from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class MedicationAdministration(Base):
    __tablename__ = "medication_administrations"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    medication_id = Column("medication_id", UUID(as_uuid=True), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    administered_at = Column("administered_at", DateTime(timezone=True), nullable=False)
    dose = Column("dose", Text)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
