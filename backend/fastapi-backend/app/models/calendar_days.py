from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class CalendarDay(Base):
    __tablename__ = "calendar_days"
    id = Column(Integer, primary_key=True, autoincrement=True)
    calendar_id = Column("calendar_id", GUID(), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False)
    date = Column("date", Date, nullable=False)
    day_type = Column("day_type", Text, nullable=False, server_default=text("'instructional'"))
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("calendar_id", "date", name="uq_calendar_day"), )
