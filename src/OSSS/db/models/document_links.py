from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import ClassVar

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class DocumentLink(UUIDMixin, Base):
    __tablename__ = "document_links"
    __allow_unmapped__ = True  # prevent SQLA from trying to map NOTE

    NOTE: ClassVar[str] = (
        "owner=division_of_technology_data; "
        "description=Stores document links records for the application. "
        "References related entities via: document, entity. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores document links records for the application. "
            "References related entities via: document, entity. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores document links records for the application. "
                "References related entities via: document, entity. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
            ),
        },
    }

    document_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)  # polymorphic target type
    entity_id: Mapped[str] = mapped_column(GUID(), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
    )

