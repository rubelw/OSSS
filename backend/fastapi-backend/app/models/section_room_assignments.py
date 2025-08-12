from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class SectionRoomAssignment(Base):
        __tablename__ = "section_room_assignments"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
section_id = Column("section_id", UUID(as_uuid=True), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
room_id = Column("room_id", UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
start_date = Column("start_date", Date)
end_date = Column("end_date", Date)
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
__table_args__ = (UniqueConstraint("section_id", "room_id", "start_date", name="uq_section_room_range"), )
