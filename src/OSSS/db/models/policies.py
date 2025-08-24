from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Policy(UUIDMixin, Base):
    __tablename__ = "policies"

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[Optional[str]] = mapped_column(sa.String(64))
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, server_default=sa.text("'active'")
    )

    versions: Mapped[List["PolicyVersion"]]= relationship(
        "PolicyVersion",
        back_populates="policy",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PolicyVersion.version_no",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_policies_org", "org_id"),
    )
