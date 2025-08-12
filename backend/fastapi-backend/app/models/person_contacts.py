from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class PersonContact(Base):
    __tablename__ = "person_contacts"
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    contact_id = Column("contact_id", GUID(), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    label = Column("label", Text)
    is_primary = Column("is_primary", Boolean, nullable=False, server_default=text("false"))
    is_emergency = Column("is_emergency", Boolean, nullable=False, server_default=text("false"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
