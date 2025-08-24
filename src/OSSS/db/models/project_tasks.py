from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class ProjectTask(UUIDMixin, Base):
    __tablename__ = "project_tasks"

    project_id = sa.Column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = sa.Column(sa.String(255), nullable=False)
    status = sa.Column(sa.String(32))
    start_date = sa.Column(sa.Date)
    end_date = sa.Column(sa.Date)
    percent_complete = sa.Column(sa.Numeric(5, 2))
    assignee_user_id = sa.Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    project = relationship("Project", back_populates="tasks")
