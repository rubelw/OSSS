from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class SisImportJob(UUIDMixin, Base):
    __tablename__ = "sis_import_jobs"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores sis import jobs records for the application. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores sis import jobs records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores sis import jobs records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    source: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=text("'running'"))
    started_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    counts: Mapped[Optional[dict]] = mapped_column(JSONB())
    error_log: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


