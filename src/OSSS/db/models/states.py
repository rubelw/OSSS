from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class State(Base):
    __tablename__ = "states"

    code: Mapped[str] = mapped_column(sa.String(2), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"State(code={self.code!r}, name={self.name!r})"
