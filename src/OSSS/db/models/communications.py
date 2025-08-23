# src/OSSS/db/models/communications.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, GUID, UUIDMixin, TimestampMixin


# -------------------------------
# Channels
# -------------------------------
class Channel(UUIDMixin, Base):
    __tablename__ = "channels"

    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(16), nullable=False, server_default=sa.text("'public'"))  # public|staff|board
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="channel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    pages: Mapped[list["Page"]] = relationship(
        "Page",
        back_populates="channel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription",
        back_populates="channel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# -------------------------------
# Posts
# -------------------------------
class Post(UUIDMixin, Base):
    __tablename__ = "posts"

    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=sa.text("'draft'"))  # draft|scheduled|published
    publish_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    author_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
    )

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="posts")
    attachments: Mapped[list["PostAttachment"]] = relationship(
        "PostAttachment",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    deliveries: Mapped[list["Delivery"]] = relationship(
        "Delivery",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# -------------------------------
# Post Attachments (association)
# -------------------------------
class PostAttachment(Base):
    __tablename__ = "post_attachments"

    post_id: Mapped[str] = mapped_column(GUID(), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    file_id: Mapped[str] = mapped_column(GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="attachments")
    # Optionally: file = relationship("File")


# -------------------------------
# Subscriptions (composite PK)
# -------------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True)
    principal_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[str] = mapped_column(GUID(), primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="subscriptions")


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
    post: Mapped["Post"] = relationship("Post", back_populates="deliveries")
    # Optionally: user = relationship("User")


# -------------------------------
# Pages
# -------------------------------
class Page(UUIDMixin, Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("channel_id", "slug", name="uq_pages_channel_slug"),)

    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=sa.text("'draft'"))
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="pages")


# -------------------------------
# Document Links
# -------------------------------
class DocumentLink(UUIDMixin, TimestampMixin, Base):
    """
    If you already define DocumentLink in db/models/document_links.py,
    remove this class to avoid duplication.
    """
    __tablename__ = "document_links"

    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    # created_at/updated_at come from TimestampMixin
