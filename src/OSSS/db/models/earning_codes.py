from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EarningCode(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "earning_codes"

    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)  # REG, OT, etc.
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    taxable: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())
