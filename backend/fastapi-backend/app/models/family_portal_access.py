from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class FamilyPortalAccess(Base):
    __tablename__ = "family_portal_access"
    guardian_id = Column("guardian_id", GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    permissions = Column("permissions", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
