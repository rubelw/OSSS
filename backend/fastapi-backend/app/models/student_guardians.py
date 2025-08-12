from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class StudentGuardian(Base):
    __tablename__ = "student_guardians"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    guardian_id = Column("guardian_id", GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True)
    custody = Column("custody", Text)
    is_primary = Column("is_primary", Boolean, nullable=False, server_default=text("false"))
    contact_order = Column("contact_order", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
