from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class StudentGuardian(Base):
        __tablename__ = "student_guardians"


student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
guardian_id = Column("guardian_id", UUID(as_uuid=True), ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True)
custody = Column("custody", Text)
is_primary = Column("is_primary", Boolean, nullable=False, server_default=text("false"))
contact_order = Column("contact_order", Integer)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
