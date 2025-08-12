from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from ._base import Base


class Contact(Base):
    __tablename__ = "contacts"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    type = Column("type", Text, nullable=False)
    value = Column("value", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
