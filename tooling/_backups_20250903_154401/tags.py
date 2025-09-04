from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Tag(UUIDMixin, Base):
    __tablename__ = "tags"

    label: Mapped[str] = mapped_column(sa.String(80), unique=True, nullable=False)
