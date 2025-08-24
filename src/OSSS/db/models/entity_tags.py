from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class EntityTag(Base):
    __tablename__ = "entity_tags"

    entity_type: Mapped[str] = mapped_column(sa.String(50), primary_key=True)
    entity_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    tag_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        sa.Index("ix_entity_tags_entity", "entity_type", "entity_id"),
        sa.Index("ix_entity_tags_tag", "tag_id"),
    )
