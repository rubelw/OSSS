from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class Address(Base):
    __tablename__ = "addresses"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    line1 = Column("line1", Text, nullable=False)
    line2 = Column("line2", Text)
    city = Column("city", Text, nullable=False)
    state = Column("state", Text)
    postal_code = Column("postal_code", Text)
    country = Column("country", Text)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
