from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class PolicyComment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_comments"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    visibility: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, server_default=sa.text("'public'")
    )

    __table_args__ = (
        sa.Index("ix_policy_comments_version", "policy_version_id"),
    )
