from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class Accommodation(UUIDMixin, Base):
    __tablename__ = "accommodations"
    __allow_unmapped__ = True  # optional, ignores other non-mapped attrs

    NOTE: ClassVar[str] = (
        "owner=special_education_related_services; "
        "description=Stores accommodations records for the application. "
        "References related entities via: iep plan. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores accommodations records for the application. "
            "References related entities via: iep plan. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
        ),
        "info": {
            # <- your DBML exporter reads this to emit the table-level Note
            "note": NOTE,
            # optional structured metadata for other tooling:
            "owner": "special_education_related_services",
            "description": (
                "Stores accommodations records for the application. "
                "References related entities via: iep plan. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
            ),
        },
    }

    iep_plan_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("iep_plans.id", ondelete="CASCADE"))
    applies_to: Mapped[Optional[str]] = mapped_column(sa.Text)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)



