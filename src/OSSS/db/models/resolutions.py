from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import ClassVar
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Resolution(UUIDMixin, Base):
    __tablename__ = "resolutions"

    # Constant (not mapped). Safe for SA 2.x + our exporter
    NOTE: ClassVar[str] = (
        "owner=special_education_related_services; "
        "description=Stores cic resolutions records for the application. "
        "Key attributes include title. References related entities via: meeting. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores cic resolutions records for the application. "
            "Key attributes include title. References related entities via: meeting. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
        ),
        "info": {
            # ← our DBML exporter reads this to emit a table-level Note
            "note": NOTE,
            # optional metadata you can keep for other tooling:
            "owner": "special_education_related_services",
            "description": (
                "Stores cic resolutions records for the application. "
                "Key attributes include title. References related entities via: meeting. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
            ),
        },
    }

    meeting_id     = sa.Column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    title          = sa.Column(sa.Text, nullable=False)
    summary        = sa.Column(sa.Text)
    effective_date = sa.Column(sa.Date)
    status         = sa.Column(sa.Text)  # adopted|rejected|tabled

    created_at, updated_at = ts_cols()

    meeting = relationship("Meeting", back_populates="resolutions")


