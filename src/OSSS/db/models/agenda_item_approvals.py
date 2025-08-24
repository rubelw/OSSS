from __future__ import annotations

import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class AgendaItemApproval(UUIDMixin, Base):
    __tablename__ = "agenda_item_approvals"

    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    approver_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    decision: Mapped[Optional[str]] = mapped_column(sa.String(16))
    decided_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    comment: Mapped[Optional[str]] = mapped_column(sa.Text)

    item: Mapped["AgendaItem"] = relationship("AgendaItem", lazy="joined")
    step: Mapped["AgendaWorkflowStep"] = relationship("AgendaWorkflowStep", lazy="joined")

    __table_args__ = (sa.Index("ix_agenda_item_approvals_item", "item_id"),)
