from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PolicyApproval(UUIDMixin, Base):
    __tablename__ = "policy_approvals"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id")
    )
    decision: Mapped[Optional[str]] = mapped_column(sa.String(16))
    decided_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    comment: Mapped[Optional[str]] = mapped_column(sa.Text)

    __table_args__ = (
        sa.UniqueConstraint("policy_version_id", "step_id", name="uq_policy_approval_step"),
        sa.Index("ix_policy_approvals_version", "policy_version_id"),
    )
