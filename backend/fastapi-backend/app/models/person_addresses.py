from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class PersonAddress(Base):
    __tablename__ = "person_addresses"
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    address_id = Column("address_id", GUID(), ForeignKey("addresses.id", ondelete="CASCADE"), primary_key=True)
    is_primary = Column("is_primary", Boolean, nullable=False, server_default=text("false"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
