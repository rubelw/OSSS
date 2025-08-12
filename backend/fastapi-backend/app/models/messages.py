from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column("sender_id", GUID(), ForeignKey("user_accounts.id", ondelete="SET NULL"))
    channel = Column("channel", Text, nullable=False)
    subject = Column("subject", Text)
    body = Column("body", Text)
    sent_at = Column("sent_at", DateTime(timezone=True))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
