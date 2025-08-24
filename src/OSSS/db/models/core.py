# src/OSSS/db/models/core.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSONB


# -------------------------------
# Organizations / Bodies
# -------------------------------
class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    bodies: Mapped[list["Body"]] = relationship(
        "Body",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class Body(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bodies"

    org_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(sa.String(50))

    organization: Mapped[Organization] = relationship("Organization", back_populates="bodies")

    __table_args__ = (sa.Index("ix_bodies_org", "org_id"),)


# -------------------------------
# Files
# -------------------------------
class File(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "files"

    storage_key: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    size: Mapped[Optional[int]] = mapped_column(sa.BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(sa.String(127))
    created_by: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("users.id"))


# -------------------------------
# Tags
# -------------------------------
class Tag(UUIDMixin, Base):
    __tablename__ = "tags"

    label: Mapped[str] = mapped_column(sa.String(80), unique=True, nullable=False)


class EntityTag(Base):
    __tablename__ = "entity_tags"

    entity_type: Mapped[str] = mapped_column(sa.String(50), primary_key=True)
    entity_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    tag_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        sa.Index("ix_entity_tags_entity", "entity_type", "entity_id"),
        sa.Index("ix_entity_tags_tag", "tag_id"),
    )


# -------------------------------
# Audit Log
# -------------------------------
class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_log"

    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("users.id"))

    at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    delta: Mapped[Optional[dict]] = mapped_column(JSONB())

    __table_args__ = (
        sa.Index("ix_audit_log_entity", "entity_type", "entity_id"),
        sa.Index("ix_audit_log_actor", "actor_id"),
    )


# -------------------------------
# Embeds
# -------------------------------
class Embed(UUIDMixin, Base):
    __tablename__ = "embeds"

    provider: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    url: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())


# -------------------------------
# Webhooks
# -------------------------------
class Webhook(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "webhooks"

    target_url: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(sa.String(255))
    # Store as JSON for ORM simplicity; keep ARRAY in DB via migrations if desired.
    events: Mapped[Optional[list[str]]] = mapped_column(JSONB())


# -------------------------------
# Notifications
# -------------------------------
class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB())
    read_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    __table_args__ = (sa.Index("ix_notifications_user", "user_id"),)


# -------------------------------
# Feature Flags
# -------------------------------
class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    org_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )

    __table_args__ = (sa.Index("ix_feature_flags_org", "org_id"),)


# -------------------------------
# Retention Rules
# -------------------------------
class RetentionRule(UUIDMixin, Base):
    __tablename__ = "retention_rules"

    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    policy: Mapped[dict] = mapped_column(JSONB(), nullable=False)

    __table_args__ = (sa.Index("ix_retention_rules_entity", "entity_type"),)