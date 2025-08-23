from __future__ import annotations
from typing import Optional
from datetime import datetime

from .base import ORMModel


class ChannelOut(ORMModel):
    id: str
    org_id: str
    name: str
    audience: str
    description: Optional[str] = None


class PostOut(ORMModel):
    id: str
    channel_id: str
    title: str
    body: Optional[str] = None
    status: str
    publish_at: Optional[datetime] = None
    author_id: Optional[str] = None
    created_at: datetime


class PageOut(ORMModel):
    id: str
    channel_id: str
    slug: str
    title: str
    body: Optional[str] = None
    status: str
    published_at: Optional[datetime] = None


class DeliveryOut(ORMModel):
    id: str
    post_id: str
    user_id: str
    delivered_at: Optional[datetime] = None
    medium: Optional[str] = None
    status: Optional[str] = None
