from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AssignmentCategory(UUIDMixin, Base):
    __tablename__ = "assignment_categories"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_teaching_learning_accountability; "
        "description=Stores assignment categories records for the application. "
        "Key attributes include name. "
        "References related entities via: section. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores assignment categories records for the application. "
            "Key attributes include name. "
            "References related entities via: section. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores assignment categories records for the application. "
            "Key attributes include name. "
            "References related entities via: section. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    weight: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


