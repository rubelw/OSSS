from sqlalchemy import Column, Text, DateTime, ForeignKey
from sqlalchemy.sql import text
from .base import Base, GUID, JSONB, UUIDMixin  # if your Base lives in _base.py, switch to: from ._base import Base
import uuid
import sqlalchemy as sa


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"
    actor_id = Column(GUID(), ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    action = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(GUID(), nullable=False)

    # NOTE: 'metadata' is reserved by SQLAlchemy's Declarative API.
    # Use a different *attribute* name and map it to the 'metadata' column name.
    metadata_ = Column("metadata", JSONB(), nullable=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False, default=lambda: str(uuid.uuid4()))