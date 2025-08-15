from __future__ import annotations
from datetime import datetime, date
import uuid
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, BigInteger, Text, ForeignKey, TIMESTAMP, text
from .base import Base, UUIDMixin, TimestampMixin, GUID, JSONB, TSVectorType
import sqlalchemy as sa



class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    bodies: Mapped[list["Body"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class Body(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bodies"
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String(50))
    organization: Mapped[Organization] = relationship(back_populates="bodies")

class File(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "files"
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[Optional[int]] = mapped_column(BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(String(127))
    created_by: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))

class Tag(UUIDMixin, Base):
    __tablename__ = "tags"
    label: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

class EntityTag(Base):
    __tablename__ = "entity_tags"
    entity_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    entity_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    tag_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_log"
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)  # type: ignore
    delta: Mapped[Optional[dict]] = mapped_column(JSONB())
from sqlalchemy import TIMESTAMP, text  # placed here to avoid circular imports warning

class Embed(UUIDMixin, Base):
    __tablename__ = "embeds"
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())

class Webhook(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "webhooks"
    target_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(String(255))
    # events as array of strings is modeled as JSON for ORM simplicity; keep ARRAY in DB via migration
    events: Mapped[Optional[list[str]]] = mapped_column(JSONB())

class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB())
    read_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore
from sqlalchemy import TIMESTAMP  # noqa

class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

class RetentionRule(UUIDMixin, Base):
    __tablename__ = "retention_rules"
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    policy: Mapped[dict] = mapped_column(JSONB(), nullable=False)
