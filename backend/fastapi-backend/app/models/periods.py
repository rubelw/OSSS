from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class Period(Base):
    __tablename__ = "periods"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bell_schedule_id = Column("bell_schedule_id", GUID(), ForeignKey("bell_schedules.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    start_time = Column("start_time", Time, nullable=False)
    end_time = Column("end_time", Time, nullable=False)
    sequence = Column("sequence", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
