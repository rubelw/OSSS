from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class Minutes(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "minutes"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores minutes records for the application. "
        "References related entities via: author, meeting. "
        "Includes standard audit timestamps (published_at, created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores minutes records for the application. "
            "References related entities via: author, meeting. "
            "Includes standard audit timestamps (published_at, created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores minutes records for the application. "
            "References related entities via: author, meeting. "
            "Includes standard audit timestamps (published_at, created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    content: Mapped[Optional[str]] = mapped_column(sa.Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="minutes", lazy="joined")


