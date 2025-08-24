from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class CICVote(UUIDMixin, Base):
    __tablename__ = "cic_votes"

    motion_id = sa.Column(GUID(), ForeignKey("cic_motions.id", ondelete="CASCADE"), nullable=False)
    person_id = sa.Column(GUID(), ForeignKey("persons.id",     ondelete="CASCADE"), nullable=False)
    value     = sa.Column(sa.Text, nullable=False)  # yea|nay|abstain|absent

    created_at, updated_at = ts_cols()

    __table_args__ = (UniqueConstraint("motion_id", "person_id", name="uq_cic_vote_unique"),)

    motion = relationship("CICMotion", back_populates="votes")
