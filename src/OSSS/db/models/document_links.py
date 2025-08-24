from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class DocumentLink(UUIDMixin, Base):
    __tablename__ = "document_links"

    document_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)  # polymorphic target type
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)

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

    __table_args__ = (
        sa.Index("ix_document_links_doc", "document_id"),
        sa.Index("ix_document_links_entity", "entity_type", "entity_id"),
    )
