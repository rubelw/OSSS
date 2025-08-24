from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class CICCommittee(UUIDMixin, Base):
    __tablename__ = "cic_committees"

    organization_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="SET NULL"))
    school_id   = sa.Column(GUID(), ForeignKey("schools.id",   ondelete="SET NULL"))
    name        = sa.Column(sa.Text, nullable=False)
    description = sa.Column(sa.Text)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'active'"))

    created_at, updated_at = ts_cols()

    __table_args__ = (
        sa.CheckConstraint(
            "(organization_id IS NOT NULL) OR (school_id IS NOT NULL)",
            name="ck_cic_committee_scope",
        ),
    )

    memberships = relationship(
        "CICMembership", back_populates="committee", cascade="all, delete-orphan"
    )
    meetings = relationship(
        "CICMeeting", back_populates="committee", cascade="all, delete-orphan"
    )
    proposals = relationship(
        "CICProposal", back_populates="committee", cascade="all, delete-orphan"
    )
