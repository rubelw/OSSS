from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class Student(Base):
    __tablename__ = "students"
    id = Column("id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    student_number = Column("student_number", Text, unique=True)
    graduation_year = Column("graduation_year", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
