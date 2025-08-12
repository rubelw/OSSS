from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class AttendanceDailySummary(Base):
    __tablename__ = "attendance_daily_summary"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    date = Column("date", Date, nullable=False)
    present_minutes = Column("present_minutes", Integer, nullable=False, server_default=text("0"))
    absent_minutes = Column("absent_minutes", Integer, nullable=False, server_default=text("0"))
    tardy_minutes = Column("tardy_minutes", Integer, nullable=False, server_default=text("0"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "date", name="uq_attendance_daily"), )
