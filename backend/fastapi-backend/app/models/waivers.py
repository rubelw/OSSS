from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class Waiver(Base):
    __tablename__ = "waivers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    reason = Column("reason", Text)
    amount = Column("amount", Numeric(10,2))
    granted_on = Column("granted_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
