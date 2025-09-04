from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PolicyPublication(Base):
    __tablename__ = "policy_publications"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores policy publications records for the application. "
        "References related entities via: policy version. "
        "Includes standard audit timestamps (published_at). "
        "4 column(s) defined. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores policy publications records for the application. "
            "References related entities via: policy version. "
            "Includes standard audit timestamps (published_at). "
            "4 column(s) defined. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores policy publications records for the application. "
            "References related entities via: policy version. "
            "Includes standard audit timestamps (published_at). "
            "4 column(s) defined. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), primary_key=True
    )
    published_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    public_url: Mapped[Optional[str]] = mapped_column(sa.String(1024))
    is_current: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.sql.false()
    )


