from __future__ import annotations
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from datetime import datetime
import uuid
import sqlalchemy as sa

# Cross-DB JSON type: JSONB on Postgres, JSON elsewhere (e.g., SQLite)
try:
    from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    JSONType = PGJSONB
except Exception:
    JSONType = sa.JSON

Base = declarative_base()
now_tz = sa.TIMESTAMP(timezone=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(sa.String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(now_tz, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(now_tz, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

class Body(Base):
    __tablename__ = "bodies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    type: Mapped[str | None] = mapped_column(sa.String(50))

class File(Base):
    __tablename__ = "files"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    storage_key: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    size: Mapped[int | None] = mapped_column(sa.BigInteger)
    mime_type: Mapped[str | None] = mapped_column(sa.String(127))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), sa.ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(now_tz, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(sa.String(80), unique=True, nullable=False)

class EntityTag(Base):
    __tablename__ = "entity_tags"
    entity_type: Mapped[str] = mapped_column(sa.String(50), primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), sa.ForeignKey("users.id"))
    at: Mapped[datetime] = mapped_column(now_tz, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    delta: Mapped[dict | None] = mapped_column(JSONType)

class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("false"), nullable=False)

class RetentionRule(Base):
    __tablename__ = "retention_rules"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    policy: Mapped[dict] = mapped_column(JSONType, nullable=False)

class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_url: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    secret: Mapped[str | None] = mapped_column(sa.String(255))
    events: Mapped[list[str] | None] = mapped_column(sa.ARRAY(sa.String(64)))
    created_at: Mapped[datetime] = mapped_column(now_tz, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

class Embed(Base):
    __tablename__ = "embeds"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    url: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSONType)

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONType)
    read_at: Mapped[datetime | None] = mapped_column(now_tz)
    created_at: Mapped[datetime] = mapped_column(now_tz, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)