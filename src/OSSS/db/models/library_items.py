from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class LibraryItem(UUIDMixin, Base):
    __tablename__ = "library_items"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=teaching_instructional_support; "
        "description=Stores library items records for the application. "
        "Key attributes include title. "
        "References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores library items records for the application. "
            "Key attributes include title. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores library items records for the application. "
            "Key attributes include title. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(sa.Text)
    isbn: Mapped[Optional[str]] = mapped_column(sa.Text)
    barcode: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


