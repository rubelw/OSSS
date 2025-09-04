# src/OSSS/db/models/scan_request.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, UUIDMixin


class ScanRequest(UUIDMixin, Base):
    """
    DB model to persist inbound ticket scan attempts (request payload).
    Mirrors the API schema fields: `qr_code` and optional `location`.
    """
    __tablename__ = "scan_requests"

    # Core fields
    qr_code: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    location: Mapped[Optional[str]] = mapped_column(sa.String(255))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(),
        onupdate=sa.func.now(), nullable=False
    )
