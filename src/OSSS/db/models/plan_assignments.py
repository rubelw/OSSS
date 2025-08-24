from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PlanAssignment(Base):
    __tablename__ = "plan_assignments"

    entity_type: Mapped[str] = mapped_column(sa.String(50), primary_key=True)  # e.g., 'plan' | 'goal' | 'objective'
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    assignee_type: Mapped[str] = mapped_column(sa.String(20), primary_key=True)  # user|group|role
    assignee_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
