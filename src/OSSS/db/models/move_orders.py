from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class MoveOrder(UUIDMixin, Base):
    __tablename__ = "move_orders"

    project_id = sa.Column(GUID(), ForeignKey("projects.id", ondelete="SET NULL"))
    person_id = sa.Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    from_space_id = sa.Column(GUID(), ForeignKey("spaces.id", ondelete="SET NULL"))
    to_space_id = sa.Column(GUID(), ForeignKey("spaces.id", ondelete="SET NULL"))
    move_date = sa.Column(sa.Date)
    status = sa.Column(sa.String(32))
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    project = relationship("Project")
    from_space = relationship("Space", foreign_keys=[from_space_id])
    to_space = relationship("Space", foreign_keys=[to_space_id])
