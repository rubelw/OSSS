from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class RetentionRule(UUIDMixin, Base):
    __tablename__ = "retention_rules"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores retention rules records for the application. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores retention rules records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores retention rules records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    policy: Mapped[dict] = mapped_column(JSONB(), nullable=False)
