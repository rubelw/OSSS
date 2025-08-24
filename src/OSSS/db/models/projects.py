from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Project(UUIDMixin, Base):
    __tablename__ = "projects"

    school_id = sa.Column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    name = sa.Column(sa.String(255), nullable=False)
    project_type = sa.Column(sa.String(32))
    status = sa.Column(sa.String(32))
    start_date = sa.Column(sa.Date)
    end_date = sa.Column(sa.Date)
    budget = sa.Column(sa.Numeric(14, 2))
    description = sa.Column(sa.Text)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")
