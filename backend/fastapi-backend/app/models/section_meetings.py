from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class SectionMeeting(Base):
    __tablename__ = "section_meetings"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    section_id = Column("section_id", UUID(as_uuid=True), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column("day_of_week", Integer, nullable=False)
    period_id = Column("period_id", UUID(as_uuid=True), ForeignKey("periods.id", ondelete="SET NULL"))
    room_id = Column("room_id", UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="SET NULL"))
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    __table_args__ = (UniqueConstraint("section_id", "day_of_week", "period_id", name="uq_section_meeting"), )
