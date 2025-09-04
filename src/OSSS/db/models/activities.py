from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class Activity(UUIDMixin, Base):
    """A club, team, group (e.g., Drama Club, Robotics, Soccer).
        Events can optionally belong to an Activity.
        """

    __tablename__ = "activities"
    __allow_unmapped__ = True  # optional, helps ignore any other non-mapped attrs

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment; "
        "description=Stores activities records for the application. "
        "Key attributes include name. References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores activities records for the application. "
            "Key attributes include name. References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
        ),
        "info": {
            # DBML exporter reads this to emit the table-level Note
            "note": NOTE,
            # optional structured metadata for other tooling
            "owner": "athletics_activities_enrichment",
            "description": (
                "Stores activities records for the application. "
                "Key attributes include name. References related entities via: school. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
            ),
        },
    }

    school_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_active: Mapped[bool] = mapped_column(sa.Text, server_default=sa.text("1"), nullable=False)
    created_at, updated_at = ts_cols()

    events: Mapped[list["Event"]] = relationship(back_populates="activity", cascade="all, delete-orphan")



