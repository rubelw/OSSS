from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class ImmunizationRecord(Base):
        __tablename__ = "immunization_records"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
immunization_id = Column("immunization_id", UUID(as_uuid=True), ForeignKey("immunizations.id", ondelete="CASCADE"), nullable=False)
date_administered = Column("date_administered", Date, nullable=False)
dose_number = Column("dose_number", Integer)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
__table_args__ = (UniqueConstraint("student_id", "immunization_id", "date_administered", name="uq_immunization_record"), )
