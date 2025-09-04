from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationSignoff(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_signoffs"

    assignment_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False
    )
    signer_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("users.id"), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(sa.Text)

    assignment: Mapped["EvaluationAssignment"] = relationship("EvaluationAssignment", back_populates="signoffs")
