from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Facility(UUIDMixin, Base):
    __tablename__ = "facilities"

    school_id = sa.Column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = sa.Column(sa.String(255), nullable=False)
    code = sa.Column(sa.String(64), unique=True)
    address = sa.Column(JSONB, nullable=True)
    attributes = sa.Column(JSONB, nullable=True)
    created_at, updated_at = ts_cols()

    buildings = relationship("Building", back_populates="facility", cascade="all, delete-orphan")
