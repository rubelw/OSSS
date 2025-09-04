# OSSS/db/models/plan_assignment.py
from __future__ import annotations

import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, text

from OSSS.db.base import Base, GUID
from typing import ClassVar

class PlanAssignment(Base):
    __tablename__ = "plan_assignments"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores plan assignments records for the application. "
        "References related entities via: assignee, entity. "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores plan assignments records for the application. "
            "References related entities via: assignee, entity. "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores plan assignments records for the application. "
            "References related entities via: assignee, entity. "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )

    # e.g., 'plan' | 'goal' | 'objective'
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    entity_id:   Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)

    # e.g., 'user' | 'group' | 'role'
    assignee_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    assignee_id:   Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
