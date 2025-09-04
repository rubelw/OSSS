from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class PMWorkGenerator(UUIDMixin, Base):
    __tablename__ = "pm_work_generators"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores pm work generators records for the application. "
        "References related entities via: pm plan. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores pm work generators records for the application. "
            "References related entities via: pm plan. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores pm work generators records for the application. "
            "References related entities via: pm plan. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    pm_plan_id = sa.Column(GUID(), ForeignKey("pm_plans.id", ondelete="CASCADE"), nullable=False)
    last_generated_at = sa.Column(sa.TIMESTAMP(timezone=True))
    lookahead_days = sa.Column(sa.Integer)
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    plan = relationship("PMPlan", back_populates="generators")


