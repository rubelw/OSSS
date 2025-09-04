from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationSignoff(UUIDMixin, TimestampMixin, Base):
    note: str = 'owner=division_of_technology_data; description=Stores evaluation signoffs records for the application. References related entities via: assignment, signer. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.'

    __tablename__ = "evaluation_signoffs"

    __table_args__ = {'comment': 'Stores evaluation signoffs records for the application. References related entities via: assignment, signer. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.', 'info': {'description': 'Stores evaluation signoffs records for the application. References related entities via: assignment, signer. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.'}}

    assignment_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False
    )
    signer_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("users.id"), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(sa.Text)

    assignment: Mapped["EvaluationAssignment"] = relationship("EvaluationAssignment", back_populates="signoffs")



