from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Channel(UUIDMixin, Base):
    __tablename__ = "channels"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_communications_engagement; "
        "description=Stores channels records for the application. "
        "Key attributes include name. "
        "References related entities via: org. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores channels records for the application. "
            "Key attributes include name. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores channels records for the application. "
            "Key attributes include name. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    audience: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'public'"))  # public|staff|board
    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    # Relationships
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="channel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    pages = sa.orm.relationship(
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


