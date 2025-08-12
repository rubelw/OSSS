from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class Staff(Base):
    __tablename__ = "staff"
    id = Column("id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    employee_number = Column("employee_number", Text, unique=True)
    title = Column("title", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
