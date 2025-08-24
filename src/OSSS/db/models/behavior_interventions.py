from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class BehaviorIntervention(UUIDMixin, Base):
    __tablename__ = "behavior_interventions"

    student_id = sa.Column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    intervention = sa.Column(sa.Text, nullable=False)
    start_date = sa.Column(sa.Date, nullable=False)
    end_date = sa.Column(sa.Date)

    created_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()
    )
