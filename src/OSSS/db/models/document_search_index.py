from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TSVectorType

class DocumentSearchIndex(Base):
    __tablename__ = "document_search_index"

    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    # With sqlalchemy-utils TSVectorType you can pass column names (e.g., TSVectorType('title'))
    # Our fallback maps to TSVECTOR on PG or TEXT elsewhere.
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    document: Mapped["Document"] = relationship("Document", back_populates="search_index", lazy="joined")

    __table_args__ = (
        sa.Index("ix_document_search_gin", "ts", postgresql_using="gin"),
    )
