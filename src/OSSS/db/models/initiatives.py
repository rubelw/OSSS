from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Initiative(UUIDMixin, Base):
    __tablename__ = "initiatives"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores initiatives records for the application. "
        "Key attributes include name. "
        "References related entities via: objective, owner. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores initiatives records for the application. "
            "Key attributes include name. "
            "References related entities via: objective, owner. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores initiatives records for the application. "
            "Key attributes include name. "
            "References related entities via: objective, owner. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    objective_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    due_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))
    priority: Mapped[Optional[str]] = mapped_column(sa.String(16))

    objective: Mapped["Objective"] = relationship("Objective", back_populates="initiatives", lazy="joined")
    owner: Mapped[Optional["User"]] = relationship("User", lazy="joined")  # type: ignore[name-defined]
