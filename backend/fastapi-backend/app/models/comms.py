from __future__ import annotations
from datetime import datetime, date

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean, TIMESTAMP, ForeignKey
from .base import Base, UUIDMixin, GUID, TSVectorType
import uuid
import sqlalchemy as sa


class Channel(UUIDMixin, Base):
    __tablename__ = "channels"
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(16), nullable=False, default="public")
    description: Mapped[Optional[str]] = mapped_column(Text)

class Post(UUIDMixin, Base):
    __tablename__ = "posts"
    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    publish_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore
    author_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # type: ignore

class PostAttachment(Base):
    __tablename__ = "post_attachments"
    post_id: Mapped[str] = mapped_column(GUID(), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    file_id: Mapped[str] = mapped_column(GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)

class Subscription(Base):
    __tablename__ = "subscriptions"
    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True)
    principal_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # type: ignore

class Delivery(UUIDMixin, Base):
    __tablename__ = "deliveries"
    post_id: Mapped[str] = mapped_column(GUID(), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore
    medium: Mapped[Optional[str]] = mapped_column(String(16))  # email|push|rss
    status: Mapped[Optional[str]] = mapped_column(String(16))

class Page(UUIDMixin, Base):
    __tablename__ = "pages"
    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore

class CommSearchIndex(Base):
    __tablename__ = "comm_search_index"
    entity_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())
