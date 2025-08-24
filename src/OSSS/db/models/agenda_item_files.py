from __future__ import annotations

import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class AgendaItemFile(Base):
    __tablename__ = "agenda_item_files"

    agenda_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )
    caption: Mapped[Optional[str]] = mapped_column(sa.String(255))
