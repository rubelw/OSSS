from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TSVectorType

class PlanSearchIndex(Base):
    __tablename__ = "plan_search_index"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores plan search index records for the application. "
        "References related entities via: plan. "
        "2 column(s) defined. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores plan search index records for the application. "
            "References related entities via: plan. "
            "2 column(s) defined. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores plan search index records for the application. "
            "References related entities via: plan. "
            "2 column(s) defined. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    plan: Mapped["Plan"] = relationship("Plan", back_populates="search_index", lazy="joined")
