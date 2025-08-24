from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PolicyLegalRef(UUIDMixin, Base):
    __tablename__ = "policy_legal_refs"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    citation: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(sa.String(1024))

    __table_args__ = (
        sa.Index("ix_policy_legal_refs_version", "policy_version_id"),
    )
