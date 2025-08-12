from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class Message(Base):
        __tablename__ = "messages"


id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
sender_id = Column("sender_id", UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL"))
channel = Column("channel", Text, nullable=False)
subject = Column("subject", Text)
body = Column("body", Text)
sent_at = Column("sent_at", DateTime(timezone=True))
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
