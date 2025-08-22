from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class Consequence(Base):
    __tablename__ = "consequences"
    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column("incident_id", GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column("participant_id", GUID(), ForeignKey("incident_participants.id", ondelete="CASCADE"), nullable=False)
    consequence_code = Column("consequence_code", Text, ForeignKey("consequence_types.code", ondelete="RESTRICT"), nullable=False)
    start_date = Column("start_date", Date)
    end_date = Column("end_date", Date)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
