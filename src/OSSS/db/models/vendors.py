from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class Vendor(UUIDMixin, Base):
    __tablename__ = "vendors"

    name = sa.Column(sa.String(255), nullable=False, unique=True)
    contact = sa.Column(JSONB, nullable=True)
    active = sa.Column(sa.Boolean, nullable=False, server_default=text("true"))
    notes = sa.Column(sa.Text)
    created_at, updated_at = ts_cols()

    warranties = relationship("Warranty", back_populates="vendor")
