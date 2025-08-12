from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
    from sqlalchemy.dialects.postgresql import UUID, JSONB
    from sqlalchemy.orm import relationship
    from ._base import Base


    class MessageRecipient(Base):
        __tablename__ = "message_recipients"


message_id = Column("message_id", UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
person_id = Column("person_id", UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
delivery_status = Column("delivery_status", Text)
delivered_at = Column("delivered_at", DateTime(timezone=True))
created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
