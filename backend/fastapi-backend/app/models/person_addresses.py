from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class PersonAddress(Base):
        __tablename__ = "person_addresses"


person_id = Column("person_id", UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
address_id = Column("address_id", UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="CASCADE"), primary_key=True)
is_primary = Column("is_primary", Boolean, nullable=False, server_default=text("false"))
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
