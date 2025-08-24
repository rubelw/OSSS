from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class PolicyVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_versions"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    content: Mapped[Optional[str]] = mapped_column(sa.Text)
    effective_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    supersedes_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="SET NULL")
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id")
    )

    policy: Mapped["Policy"] = relationship(
        "Policy", back_populates="versions", lazy="joined"
    )
    supersedes: Mapped[Optional["PolicyVersion"]] = relationship(
        "PolicyVersion",
        remote_side="PolicyVersion.id",
        lazy="joined",
        viewonly=True,
    )

    __table_args__ = (
        sa.Index("ix_policy_versions_policy", "policy_id"),
    )
