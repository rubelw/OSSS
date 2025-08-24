from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Consent(UUIDMixin, Base):
    __tablename__ = "consents"

    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    consent_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    granted: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("true"))
    effective_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    expires_on: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("person_id", "consent_type", name="uq_consent_type"),)
