from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class MoveOrder(UUIDMixin, Base):
    __tablename__ = "move_orders"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores move orders records for the application. "
        "References related entities via: from space, person, project, to space. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "4 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores move orders records for the application. "
            "References related entities via: from space, person, project, to space. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "4 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores move orders records for the application. "
            "References related entities via: from space, person, project, to space. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "4 foreign key field(s) detected."
        ),
        },
    }


    project_id = sa.Column(GUID(), ForeignKey("projects.id", ondelete="SET NULL"))
    person_id = sa.Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    from_space_id = sa.Column(GUID(), ForeignKey("spaces.id", ondelete="SET NULL"))
    to_space_id = sa.Column(GUID(), ForeignKey("spaces.id", ondelete="SET NULL"))
    move_date = sa.Column(sa.Date)
    status = sa.Column(sa.String(32))
    attributes = sa.Column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    project = relationship("Project")
    from_space = relationship("Space", foreign_keys=[from_space_id])
    to_space = relationship("Space", foreign_keys=[to_space_id])


