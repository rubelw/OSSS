from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class GLAccount(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gl_accounts"

    code: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)  # full combined code
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    acct_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # asset, liability, revenue, expense, equity
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    lines: Mapped[list["JournalEntryLine"]] = relationship("JournalEntryLine", back_populates="account")
