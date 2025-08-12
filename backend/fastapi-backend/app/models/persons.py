from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class Person(Base):
    __tablename__ = "persons"
    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column("first_name", Text, nullable=False)
    last_name = Column("last_name", Text, nullable=False)
    middle_name = Column("middle_name", Text)
    dob = Column("dob", Date)
    email = Column("email", Text)
    phone = Column("phone", Text)
    gender = Column("gender", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
