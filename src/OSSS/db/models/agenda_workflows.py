from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AgendaWorkflow(UUIDMixin, Base):
    __tablename__ = "agenda_workflows"

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))

    steps: Mapped[List["AgendaWorkflowStep"]] = relationship(
        "AgendaWorkflowStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="AgendaWorkflowStep.step_no",
    )
