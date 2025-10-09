from __future__ import annotations
from typing import Optional, List
from datetime import datetime

from .base import ORMModel, TimestampMixin


# Organization / Body
class OrganizationBase(ORMModel):
    name: str


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationOut(OrganizationBase, TimestampMixin):
    id: str


class BodyBase(ORMModel):
    org_id: str
    name: str
    type: Optional[str] = None


class BodyCreate(BodyBase):
    pass


class BodyOut(BodyBase, TimestampMixin):
    id: str


# File
class FileBase(ORMModel):
    storage_key: str
    filename: str
    size: Optional[int] = None
    mime_type: Optional[str] = None
    created_by: Optional[str] = None


class FileCreate(FileBase):
    pass


class FileOut(FileBase, TimestampMixin):
    id: str


# Tags
class TagBase(ORMModel):
    label: str


class TagCreate(TagBase):
    pass


class TagOut(TagBase):
    id: str


# EntityTag
class EntityTagBase(ORMModel):
    entity_type: str
    entity_id: str
    tag_id: str


class EntityTagOut(EntityTagBase):
    pass


# AuditLog (core)
class AuditLogOut(ORMModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    actor_id: Optional[str] = None
    at: datetime
    delta: Optional[dict] = None


# Embed
class EmbedBase(ORMModel):
    provider: str
    url: str
    meta: Optional[dict] = None


class EmbedCreate(EmbedBase):
    pass


class EmbedOut(EmbedBase):
    id: str


# Webhook
class WebhookBase(ORMModel):
    target_url: str
    secret: Optional[str] = None
    events: Optional[list[str]] = None


class WebhookCreate(WebhookBase):
    pass


class WebhookOut(WebhookBase, TimestampMixin):
    id: str


# Notification
class NotificationBase(ORMModel):
    user_id: str
    type: str
    payload: Optional[dict] = None
    read_at: Optional[datetime] = None


class NotificationOut(NotificationBase, TimestampMixin):
    id: str


# FeatureFlag
class FeatureFlagBase(ORMModel):
    org_id: str
    key: str
    enabled: bool = False


class FeatureFlagOut(FeatureFlagBase):
    pass


# RetentionRule
class RetentionRuleBase(ORMModel):
    entity_type: str
    policy: dict


class RetentionRuleCreate(RetentionRuleBase):
    pass


class RetentionRuleOut(RetentionRuleBase):
    id: str
