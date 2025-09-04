from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class MedicationAdministration(UUIDMixin, Base):
    __tablename__ = "medication_administrations"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    medication_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    administered_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    dose: Mapped[Optional[str]] = mapped_column(sa.Text)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
