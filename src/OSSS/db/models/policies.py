from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Policy(UUIDMixin, Base):
    __tablename__ = "policies"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores policies records for the application. "
        "Key attributes include code, title. "
        "References related entities via: org. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores policies records for the application. "
            "Key attributes include code, title. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores policies records for the application. "
            "Key attributes include code, title. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False
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
