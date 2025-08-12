from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class Consent(Base):
    __tablename__ = "consents"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    person_id = Column("person_id", UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    consent_type = Column("consent_type", Text, nullable=False)
    granted = Column("granted", Boolean, nullable=False, server_default=text("true"))
    effective_date = Column("effective_date", Date, nullable=False)
    expires_on = Column("expires_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    __table_args__ = (UniqueConstraint("person_id", "consent_type", name="uq_consent_type"), )
