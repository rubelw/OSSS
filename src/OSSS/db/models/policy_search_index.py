from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TSVectorType

class PolicySearchIndex(Base):
    __tablename__ = "policy_search_index"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores policy search index records for the application. "
        "References related entities via: policy. "
        "2 column(s) defined. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores policy search index records for the application. "
            "References related entities via: policy. "
            "2 column(s) defined. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores policy search index records for the application. "
            "References related entities via: policy. "
            "2 column(s) defined. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    policy_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())
