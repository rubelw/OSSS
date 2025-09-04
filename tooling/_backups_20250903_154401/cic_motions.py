from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class CICMotion(UUIDMixin, Base):
    __tablename__ = "cic_motions"

    agenda_item_id = sa.Column(GUID(), ForeignKey("cic_agenda_items.id", ondelete="CASCADE"), nullable=False)
    text           = sa.Column(sa.Text, nullable=False)
    moved_by_id    = sa.Column(GUID(), ForeignKey("persons.id", ondelete="SET NULL"))
    seconded_by_id = sa.Column(GUID(), ForeignKey("persons.id", ondelete="SET NULL"))
    result         = sa.Column(sa.Text)  # passed|failed|tabled
    tally_for      = sa.Column(sa.Integer)
    tally_against  = sa.Column(sa.Integer)
    tally_abstain  = sa.Column(sa.Integer)

    created_at, updated_at = ts_cols()

    agenda_item = relationship("CICAgendaItem", back_populates="motions")
    votes = relationship("CICVote", back_populates="motion", cascade="all, delete-orphan")
