from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class WorkOrderTask(UUIDMixin, Base):
    __tablename__ = "work_order_tasks"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_operations; "
        "description=Stores work order tasks records for the application. "
        "Key attributes include title. "
        "References related entities via: work order. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores work order tasks records for the application. "
            "Key attributes include title. "
            "References related entities via: work order. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores work order tasks records for the application. "
            "Key attributes include title. "
            "References related entities via: work order. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    work_order_id = sa.Column(GUID(), ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    seq = sa.Column(sa.Integer, nullable=False, server_default=text("1"))
    title = sa.Column(sa.String(255), nullable=False)
    is_mandatory = sa.Column(sa.Text, nullable=False, server_default=text("0"))
    status = sa.Column(sa.String(32))
    completed_at = sa.Column(sa.TIMESTAMP(timezone=True))
    notes = sa.Column(sa.Text)
    created_at, updated_at = ts_cols()

    work_order = relationship("WorkOrder", back_populates="tasks")


