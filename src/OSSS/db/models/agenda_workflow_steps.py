from __future__ import annotations

import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AgendaWorkflowStep(UUIDMixin, Base):
    __tablename__ = "agenda_workflow_steps"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores agenda workflow steps records for the application. "
        "References related entities via: approver, workflow. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores agenda workflow steps records for the application. "
            "References related entities via: approver, workflow. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores agenda workflow steps records for the application. "
            "References related entities via: approver, workflow. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_workflows.id", ondelete="CASCADE"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    approver_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    rule: Mapped[Optional[str]] = mapped_column(sa.String(255))

    workflow: Mapped["AgendaWorkflow"] = relationship("AgendaWorkflow", back_populates="steps", lazy="joined")
