from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class EvaluationFile(Base):
    __tablename__ = "evaluation_files"

    assignment_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), primary_key=True
    )
    file_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
