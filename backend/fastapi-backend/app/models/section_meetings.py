from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class SectionMeeting(Base):
    __tablename__ = "section_meetings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column("day_of_week", Integer, nullable=False)
    period_id = Column("period_id", GUID(), ForeignKey("periods.id", ondelete="SET NULL"))
    room_id = Column("room_id", GUID(), ForeignKey("rooms.id", ondelete="SET NULL"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("section_id", "day_of_week", "period_id", name="uq_section_meeting"), )
