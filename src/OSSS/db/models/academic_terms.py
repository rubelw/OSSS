from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class AcademicTerm(UUIDMixin, Base):
    __tablename__ = "academic_terms"
    __allow_unmapped__ = True  # optional, helps ignore other non-mapped attrs

    NOTE: ClassVar[str] = (
        "owner=division_of_teaching_learning_accountability; "
        "description=Stores academic terms records for the application. "
        "Key attributes include name. References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores academic terms records for the application. "
            "Key attributes include name. References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
        ),
        "info": {
            # DBML exporter reads this to emit table-level Note
            "note": NOTE,
            # Optional structured metadata:
            "owner": "division_of_teaching_learning_accountability",
            "description": (
                "Stores academic terms records for the application. "
                "Key attributes include name. References related entities via: school. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
            ),
        },
    }

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(sa.Text)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)



