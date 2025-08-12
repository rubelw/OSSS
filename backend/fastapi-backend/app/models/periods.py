from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class Period(Base):
    __tablename__ = "periods"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    bell_schedule_id = Column("bell_schedule_id", UUID(as_uuid=True), ForeignKey("bell_schedules.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    start_time = Column("start_time", Time, nullable=False)
    end_time = Column("end_time", Time, nullable=False)
    sequence = Column("sequence", Integer)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
