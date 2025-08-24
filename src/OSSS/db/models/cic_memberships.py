from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class CICMembership(UUIDMixin, Base):
    __tablename__ = "cic_memberships"

    committee_id  = sa.Column(GUID(), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    person_id     = sa.Column(GUID(), ForeignKey("persons.id",        ondelete="CASCADE"), nullable=False)
    role          = sa.Column(sa.Text)  # chair, member, etc.
    start_date    = sa.Column(sa.Date)
    end_date      = sa.Column(sa.Date)
    voting_member = sa.Column(sa.Boolean, nullable=False, server_default=text("true"))

    created_at, updated_at = ts_cols()

    __table_args__ = (UniqueConstraint("committee_id", "person_id", name="uq_cic_membership_unique"),)

    committee = relationship("CICCommittee", back_populates="memberships")
