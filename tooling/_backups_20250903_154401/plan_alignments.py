from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PlanAlignment(UUIDMixin, Base):
    __tablename__ = "plan_alignments"

    agenda_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="SET NULL")
    )
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="SET NULL")
    )
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("objectives.id", ondelete="SET NULL")
    )
    note: Mapped[Optional[str]] = mapped_column(sa.Text)

    agenda_item: Mapped[Optional["AgendaItem"]] = relationship("AgendaItem", lazy="joined")  # type: ignore[name-defined]
    policy: Mapped[Optional["Policy"]] = relationship("Policy", lazy="joined")              # type: ignore[name-defined]
    objective: Mapped[Optional["Objective"]] = relationship("Objective", lazy="joined")
