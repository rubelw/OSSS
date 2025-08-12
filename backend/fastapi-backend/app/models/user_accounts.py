from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class UserAccount(Base):
    __tablename__ = "user_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    username = Column("username", Text, nullable=False, unique=True)
    password_hash = Column("password_hash", Text)
    is_active = Column("is_active", Boolean, nullable=False, server_default=text("true"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
