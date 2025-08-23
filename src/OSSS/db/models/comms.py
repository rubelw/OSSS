# src/OSSS/db/models/comms.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import String, Text, Boolean, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, UUIDMixin, GUID, TSVectorType


class Channel(UUIDMixin, Base):
    __tablename__ = "channels"

    org_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # public | staff | board — default to public
    audience: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa.text("'public'")
    )
    description: Mapped[Optional[str]] = mapped_column(Text)


class Post(UUIDMixin, Base):
    __tablename__ = "posts"

    channel_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    # draft | scheduled | published — default to draft
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa.text("'draft'")
    )
    publish_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    author_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
    )


class PostAttachment(Base):
    __tablename__ = "post_attachments"

    post_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    channel_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    # user | group | role
    principal_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    principal_id: Mapped[str] = mapped_column(GUID(), primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class Delivery(UUIDMixin, Base):
    __tablename__ = "deliveries"

    post_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    # email | push | rss
    medium: Mapped[Optional[str]] = mapped_column(String(16))
    # sent | failed | opened
    status: Mapped[Optional[str]] = mapped_column(String(16))


class Page(UUIDMixin, Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("channel_id", "slug", name="uq_pages_channel_slug"),)

    channel_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=sa.text("'draft'")
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class CommSearchIndex(Base):
    __tablename__ = "comm_search_index"

    entity_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())
