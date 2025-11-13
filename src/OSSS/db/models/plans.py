from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Plan(UUIDMixin, Base):
    __tablename__ = "plans"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores plans records for the application. "
        "Key attributes include name. "
        "References related entities via: org. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores plans records for the application. "
            "Key attributes include name. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores plans records for the application. "
            "Key attributes include name. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    cycle_start: Mapped[Optional[date]] = mapped_column(sa.Date)
    cycle_end: Mapped[Optional[date]] = mapped_column(sa.Date)
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))

    goals: Mapped[List["Goal"]] = relationship(
        "Goal",
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Goal.name",
        lazy="selectin",
    )

    # Optional: a single search row per plan
    search_index: Mapped[Optional["PlanSearchIndex"]] = relationship(
        "PlanSearchIndex",
        back_populates="plan",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )
