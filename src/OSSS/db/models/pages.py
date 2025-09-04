from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Page(UUIDMixin, Base):
    __tablename__ = "pages"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores pages records for the application. "
        "Key attributes include slug, title. "
        "References related entities via: channel. "
        "Includes standard audit timestamps (published_at, created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores pages records for the application. "
            "Key attributes include slug, title. "
            "References related entities via: channel. "
            "Includes standard audit timestamps (published_at, created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores pages records for the application. "
            "Key attributes include slug, title. "
            "References related entities via: channel. "
            "Includes standard audit timestamps (published_at, created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }

    slug: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'draft'"))
    published_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    # Relationships
    channel_id = sa.Column(
        GUID,
        sa.ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel = sa.orm.relationship("Channel", back_populates="pages")
