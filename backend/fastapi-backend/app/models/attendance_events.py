from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from ._base import Base


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_meeting_id = Column("section_meeting_id", UUID(as_uuid=True), ForeignKey("section_meetings.id", ondelete="SET NULL"))
    date = Column("date", Date, nullable=False)
    code = Column("code", Text, ForeignKey("attendance_codes.code", ondelete="RESTRICT"), nullable=False)
    minutes = Column("minutes", Integer)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "date", "section_meeting_id", name="uq_attendance_event"), )
