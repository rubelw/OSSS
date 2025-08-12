from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class UserAccount(Base):
    __tablename__ = "user_accounts"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    person_id = Column("person_id", UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    username = Column("username", Text, nullable=False, unique=True)
    password_hash = Column("password_hash", Text)
    is_active = Column("is_active", Boolean, nullable=False, server_default=text("true"))
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
