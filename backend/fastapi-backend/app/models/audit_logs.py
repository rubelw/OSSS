from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from ._base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    actor_id = Column("actor_id", UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL"))
    action = Column("action", Text, nullable=False)
    entity_type = Column("entity_type", Text, nullable=False)
    entity_id = Column("entity_id", UUID(as_uuid=True), nullable=False)
    metadata = Column("metadata", JSONB)
    occurred_at = Column("occurred_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
