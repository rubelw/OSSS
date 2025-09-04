# The purpose of the `Embed` model is to represent external media or content
# (like videos, audio tracks, design links, etc.) that can be attached to
# or referenced from within your OSSS system.
#
# Key points:
# - Inherits from UUIDMixin and Base:
#     -> provides a unique UUID primary key (`id`) plus standard ORM mapping.
#
# - `provider`:
#     -> The service that hosts the embed (e.g., YouTube, Vimeo, Spotify).
#     -> Stored as a short string (up to 64 characters).
#
# - `url`:
#     -> The actual URL to the embedded resource.
#     -> Allows up to 1024 characters to accommodate long provider URLs.
#
# - `meta`:
#     -> A JSONB column for flexible metadata.
#     -> Can store provider-specific details (title, thumbnail, dimensions, tags).
#     -> Optional field so rows can exist with or without metadata.
#
# In practice:
# - This model provides a standardized way to reference external media inside
#   OSSS (like attaching a YouTube lecture, SoundCloud clip, Figma design, etc.).
# - The JSONB `meta` allows unstructured, provider-specific info without schema changes.
# - Useful for linking supplemental resources, multimedia content, or external
#   references directly to internal objects (courses, goals, notes, etc.).


from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Embed(UUIDMixin, Base):
    __tablename__ = "embeds"

    provider: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    url: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())
