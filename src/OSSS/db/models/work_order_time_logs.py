from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class WorkOrderTimeLog(UUIDMixin, Base):
    __tablename__ = "work_order_time_logs"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_operations; "
        "description=Stores work order time logs records for the application. "
        "References related entities via: user, work order. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "11 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores work order time logs records for the application. "
            "References related entities via: user, work order. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores work order time logs records for the application. "
            "References related entities via: user, work order. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "11 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }



    work_order_id = sa.Column(GUID(), ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    user_id = sa.Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    started_at = sa.Column(sa.TIMESTAMP(timezone=True))
    ended_at = sa.Column(sa.TIMESTAMP(timezone=True))
    hours = sa.Column(sa.Numeric(10, 2))
    hourly_rate = sa.Column(sa.Numeric(12, 2))
    cost = sa.Column(sa.Numeric(12, 2))
    notes = sa.Column(sa.Text)
    created_at, updated_at = ts_cols()

    work_order = relationship("WorkOrder", back_populates="time_logs")


