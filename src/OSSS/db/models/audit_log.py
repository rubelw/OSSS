from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_log"

    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("users.id"))

    at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    delta: Mapped[Optional[dict]] = mapped_column(JSONB())

    __table_args__ = (
        sa.Index("ix_audit_log_entity", "entity_type", "entity_id"),
        sa.Index("ix_audit_log_actor", "actor_id"),
    )
