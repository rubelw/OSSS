from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class ConsequenceType(Base):
    __tablename__ = "consequence_types"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=student_services_school_level; "
        "description=Stores consequence types records for the application. "
        "Key attributes include code. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "4 column(s) defined."
    )

    __table_args__ = {
        "comment":         (
            "Stores consequence types records for the application. "
            "Key attributes include code. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "4 column(s) defined."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores consequence types records for the application. "
            "Key attributes include code. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "4 column(s) defined."
        ),
        },
    }


    code: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
    )


