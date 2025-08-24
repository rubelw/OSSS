from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PolicyWorkflowStep(UUIDMixin, Base):
    __tablename__ = "policy_workflow_steps"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_workflows.id", ondelete="CASCADE"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    approver_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # user|group|role
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID())
    rule: Mapped[Optional[str]] = mapped_column(sa.String(50))

    workflow: Mapped["PolicyWorkflow"] = relationship(
        "PolicyWorkflow", back_populates="steps", lazy="joined"
    )

    __table_args__ = (
        sa.UniqueConstraint("workflow_id", "step_no", name="uq_policy_workflow_step_no"),
        sa.Index("ix_policy_workflow_steps_wf", "workflow_id"),
    )
