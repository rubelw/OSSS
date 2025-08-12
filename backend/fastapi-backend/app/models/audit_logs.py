from sqlalchemy import Column, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import text
from .base import Base  # if your Base lives in _base.py, switch to: from ._base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    actor_id = Column(UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    action = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    # NOTE: 'metadata' is reserved by SQLAlchemy's Declarative API.
    # Use a different *attribute* name and map it to the 'metadata' column name.
    metadata_ = Column("metadata", JSONB(astext_type=Text()), nullable=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))