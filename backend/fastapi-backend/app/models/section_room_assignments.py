from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class SectionRoomAssignment(Base):
    __tablename__ = "section_room_assignments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    room_id = Column("room_id", GUID(), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    start_date = Column("start_date", Date)
    end_date = Column("end_date", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("section_id", "room_id", "start_date", name="uq_section_room_range"), )
