from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class AttendanceCode(Base):
    __tablename__ = "attendance_codes"
    code = Column("code", Text, primary_key=True)
    description = Column("description", Text)
    is_present = Column("is_present", Boolean, nullable=False, server_default=text("false"))
    is_excused = Column("is_excused", Boolean, nullable=False, server_default=text("false"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
