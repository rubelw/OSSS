from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from ._base import Base


class Consequence(Base):
    __tablename__ = "consequences"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    incident_id = Column("incident_id", UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column("participant_id", UUID(as_uuid=True), ForeignKey("incident_participants.id", ondelete="CASCADE"), nullable=False)
    consequence_code = Column("consequence_code", Text, ForeignKey("consequence_types.code", ondelete="RESTRICT"), nullable=False)
    start_date = Column("start_date", Date)
    end_date = Column("end_date", Date)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
