from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_meeting_id = Column("section_meeting_id", GUID(), ForeignKey("section_meetings.id", ondelete="SET NULL"))
    date = Column("date", Date, nullable=False)
    code = Column("code", Text, ForeignKey("attendance_codes.code", ondelete="RESTRICT"), nullable=False)
    minutes = Column("minutes", Integer)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "date", "section_meeting_id", name="uq_attendance_event"), )
