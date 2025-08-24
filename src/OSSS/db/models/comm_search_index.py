from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TSVectorType

class CommSearchIndex(Base):
    __tablename__ = "comm_search_index"

    entity_type: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    entity_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())
