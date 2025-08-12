from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class AttendanceDailySummary(Base):
    __tablename__ = "attendance_daily_summary"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    date = Column("date", Date, nullable=False)
    present_minutes = Column("present_minutes", Integer, nullable=False, server_default=text("0"))
    absent_minutes = Column("absent_minutes", Integer, nullable=False, server_default=text("0"))
    tardy_minutes = Column("tardy_minutes", Integer, nullable=False, server_default=text("0"))
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "date", name="uq_attendance_daily"), )
