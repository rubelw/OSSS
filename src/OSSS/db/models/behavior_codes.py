from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class BehaviorCode(Base):
    __tablename__ = "behavior_codes"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_schools | student_services_school_level; "
        "description=Stores behavior codes records for the application. "
        "Key attributes include code. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "4 column(s) defined."
    )

    __table_args__ = {
        "comment":         (
            "Stores behavior codes records for the application. "
            "Key attributes include code. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "4 column(s) defined."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores behavior codes records for the application. "
            "Key attributes include code. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "4 column(s) defined."
        ),
        },
    }


    code = sa.Column(sa.Text, primary_key=True)
    description = sa.Column(sa.Text)

    created_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()
    )


