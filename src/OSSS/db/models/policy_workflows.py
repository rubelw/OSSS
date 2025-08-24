from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PolicyWorkflow(UUIDMixin, Base):
    __tablename__ = "policy_workflows"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )

    steps: Mapped[List["PolicyWorkflowStep"]] = relationship(
        "PolicyWorkflowStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PolicyWorkflowStep.step_no",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_policy_workflows_policy", "policy_id"),
    )
