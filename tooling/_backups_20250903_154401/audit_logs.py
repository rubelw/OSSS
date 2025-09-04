from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("user_accounts.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_id: Mapped[Any] = mapped_column(GUID(), nullable=False)

    # 'metadata' is reserved by SQLAlchemy; map attribute name to column "metadata"
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB())

    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
