from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class IncidentParticipant(Base):
    __tablename__ = "incident_participants"
    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column("incident_id", GUID(), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    role = Column("role", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("incident_id", "person_id", name="uq_incident_person"), )
