from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PolicyFile(Base):
    __tablename__ = "policy_files"

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )
