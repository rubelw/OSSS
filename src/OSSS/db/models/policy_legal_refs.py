from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PolicyLegalRef(UUIDMixin, Base):
    __tablename__ = "policy_legal_refs"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores policy legal refs records for the application. "
        "References related entities via: policy version. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores policy legal refs records for the application. "
            "References related entities via: policy version. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores policy legal refs records for the application. "
            "References related entities via: policy version. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False
    )
    citation: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(sa.String(1024))
