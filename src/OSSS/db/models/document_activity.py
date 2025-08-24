from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class DocumentActivity(UUIDMixin, Base):
    __tablename__ = "document_activity"

    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())

    document: Mapped["Document"] = relationship("Document", back_populates="activities", lazy="joined")

    __table_args__ = (sa.Index("ix_document_activity_doc", "document_id"),)
