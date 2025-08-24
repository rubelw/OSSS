from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class DataSharingAgreement(UUIDMixin, Base):
    __tablename__ = "data_sharing_agreements"

    vendor: Mapped[str] = mapped_column(sa.Text, nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(sa.Text)
    start_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    end_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
