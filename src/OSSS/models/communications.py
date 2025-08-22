# app/models/comms.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, GUID, UUIDMixin, TimestampMixin  # assuming these exist in your project


# -------------------------------
# Channels
# -------------------------------
class Channel(UUIDMixin, Base):
    __tablename__ = "channels"

    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(16), server_default=sa.text("'public'"), nullable=False)  # public|staff|board
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    posts: Mapped[List["Post"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    pages: Mapped[List["Page"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[List["Subscription"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


# -------------------------------
# Posts
# -------------------------------
class Post(UUIDMixin, Base):
    __tablename__ = "posts"

    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), server_default=sa.text("'draft'"), nullable=False)  # draft|scheduled|published
    publish_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    author_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
    )

    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="posts")
    attachments: Mapped[List["PostAttachment"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    deliveries: Mapped[List["Delivery"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )


# -------------------------------
# Post Attachments (association)
# -------------------------------
class PostAttachment(Base):
    __tablename__ = "post_attachments"

    post_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )

    # Relationships
    post: Mapped["Post"] = relationship(back_populates="attachments")
    # You can add a relationship to File if desired:
    # file: Mapped["File"] = relationship("File")


# -------------------------------
# Subscriptions (composite PK)
# -------------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    channel_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    principal_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
    )

    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="subscriptions")


# -------------------------------
# Deliveries
# -------------------------------
class Delivery(UUIDMixin, Base):
    __tablename__ = "deliveries"

    post_id: Mapped[str] = mapped_column(GUID(), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    medium: Mapped[Optional[str]] = mapped_column(String(16))  # email|push|rss
    status: Mapped[Optional[str]] = mapped_column(String(16))  # sent|failed|opened

    # Relationships
    post: Mapped["Post"] = relationship(back_populates="deliveries")
    # You can add a relationship to User if desired:
    # user: Mapped["User"] = relationship("User")


# -------------------------------
# Pages
# -------------------------------
class Page(UUIDMixin, Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("channel_id", "slug", name="uq_pages_channel_slug"),
    )

    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), server_default=sa.text("'draft'"), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="pages")


# -------------------------------
# Document Links
# -------------------------------
class DocumentLink(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "document_links"

    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    # TimestampMixin should provide created_at/updated_at to match *_timestamps() in migrations
