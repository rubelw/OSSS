from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List,ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class DocumentActivity(UUIDMixin, Base):
    __tablename__ = "document_activity"
    __allow_unmapped__ = True  # ignore class-level notes etc.

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores document activity records for the application. "
        "References related entities via: actor, document. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores document activity records for the application. "
            "References related entities via: actor, document. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores document activity records for the application. "
                "References related entities via: actor, document. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
            ),
        },
    }


    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())

    document: Mapped["Document"] = relationship("Document", back_populates="activities", lazy="joined")

