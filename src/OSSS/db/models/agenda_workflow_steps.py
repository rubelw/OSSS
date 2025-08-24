from __future__ import annotations

import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AgendaWorkflowStep(UUIDMixin, Base):
    __tablename__ = "agenda_workflow_steps"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_workflows.id", ondelete="CASCADE"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    approver_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    rule: Mapped[Optional[str]] = mapped_column(sa.String(50))

    workflow: Mapped["AgendaWorkflow"] = relationship("AgendaWorkflow", back_populates="steps", lazy="joined")

    __table_args__ = (sa.Index("ix_agenda_workflow_steps_wf", "workflow_id"),)
