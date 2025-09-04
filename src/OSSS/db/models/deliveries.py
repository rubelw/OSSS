from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Delivery(UUIDMixin, Base):
    __tablename__ = "deliveries"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_operations; "
        "description=Stores deliveries records for the application. "
        "References related entities via: post, user. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores deliveries records for the application. "
            "References related entities via: post, user. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores deliveries records for the application. "
            "References related entities via: post, user. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    post_id: Mapped[str] = mapped_column(GUID(), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    medium: Mapped[Optional[str]] = mapped_column(sa.String(16))  # email|push|rss
    status: Mapped[Optional[str]] = mapped_column(sa.String(16))  # sent|failed|opened

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="deliveries")


