# OSSS/db/models/plan_assignment.py
from __future__ import annotations

import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, text

from OSSS.db.base import Base, GUID

class PlanAssignment(Base):
    __tablename__ = "plan_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )

    # e.g., 'plan' | 'goal' | 'objective'
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    entity_id:   Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)

    # e.g., 'user' | 'group' | 'role'
    assignee_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    assignee_id:   Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)

    __table_args__ = (
        sa.UniqueConstraint(
            "entity_type", "entity_id", "assignee_type", "assignee_id",
            name="uq_plan_assignments_tuple",
        ),
        sa.Index("ix_plan_assignments_entity", "entity_type", "entity_id"),
        sa.Index("ix_plan_assignments_assignee", "assignee_type", "assignee_id"),
    )
