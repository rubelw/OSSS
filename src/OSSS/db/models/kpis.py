from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class KPI(UUIDMixin, Base):
    __tablename__ = "kpis"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores kpis records for the application. "
        "Key attributes include name. "
        "References related entities via: goal, objective. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores kpis records for the application. "
            "Key attributes include name. "
            "References related entities via: goal, objective. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores kpis records for the application. "
            "Key attributes include name. "
            "References related entities via: goal, objective. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    goal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="SET NULL")
    )
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("objectives.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(sa.String(32))
    target: Mapped[Optional[float]] = mapped_column(sa.Float)
    baseline: Mapped[Optional[float]] = mapped_column(sa.Float)
    direction: Mapped[Optional[str]] = mapped_column(sa.String(8))  # up|down

    goal: Mapped[Optional["Goal"]] = relationship("Goal", back_populates="kpis", lazy="joined")
    objective: Mapped[Optional["Objective"]] = relationship("Objective", back_populates="kpis", lazy="joined")

    datapoints: Mapped[List["KPIDatapoint"]] = relationship(
        "KPIDatapoint",
        back_populates="kpi",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="KPIDatapoint.as_of",
        lazy="selectin",
    )
