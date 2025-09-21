# src/OSSS/db/models/activities.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import ClassVar, Optional

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols


class Activity(UUIDMixin, Base):
    """A club, team, or group (e.g., Drama Club, Robotics, Soccer).
    Events can optionally belong to an Activity.
    """

    __tablename__ = "activities"
    __allow_unmapped__ = True  # ignore non-mapped attrs if present

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
            "note": NOTE,
            "owner": "athletics_activities_enrichment",
            "description": (
                "Stores activities records for the application. "
                "Key attributes include name. References related entities via: school. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected."
            ),
        },
    }

    # --- columns --------------------------------------------------------------
    school_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=text("true")
    )

    # timestamps
    created_at, updated_at = ts_cols()

    # --- relationships (strings to avoid import cycles) -----------------------
    school: Mapped["School"] = relationship("School")
    events: Mapped[list["Event"]] = relationship(
        "Event",
        back_populates="activity",
        cascade="all, delete-orphan",
    )
