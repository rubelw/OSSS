from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Motion(UUIDMixin, Base):
    __tablename__ = "motions"

    agenda_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    moved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    seconded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    passed: Mapped[Optional[bool]] = mapped_column(sa.Boolean)
    tally_for: Mapped[Optional[int]] = mapped_column(sa.Integer)
    tally_against: Mapped[Optional[int]] = mapped_column(sa.Integer)
    tally_abstain: Mapped[Optional[int]] = mapped_column(sa.Integer)

    agenda_item: Mapped["AgendaItem"] = relationship("AgendaItem", lazy="joined")
