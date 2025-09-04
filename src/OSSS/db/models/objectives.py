from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Objective(UUIDMixin, Base):
    __tablename__ = "objectives"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores objectives records for the application. "
        "Key attributes include name. "
        "References related entities via: goal. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores objectives records for the application. "
            "Key attributes include name. "
            "References related entities via: goal. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores objectives records for the application. "
            "Key attributes include name. "
            "References related entities via: goal. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    goal_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    goal: Mapped["Goal"] = relationship("Goal", back_populates="objectives", lazy="joined")

    initiatives: Mapped[List["Initiative"]] = relationship(
        "Initiative",
        back_populates="objective",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Initiative.name",
        lazy="selectin",
    )

    # KPIs attached to this Objective
    kpis: Mapped[List["KPI"]] = relationship(
        "KPI",
        back_populates="objective",
        primaryjoin="Objective.id == KPI.objective_id",
        lazy="selectin",
    )
