from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class MeetingDocument(UUIDMixin, Base):
    __tablename__ = "meeting_documents"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores cic meeting documents records for the application. "
        "References related entities via: document, meeting. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores meeting documents records for the application. "
            "References related entities via: document, meeting. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores meeting documents records for the application. "
            "References related entities via: document, meeting. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    meeting_id  = sa.Column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    document_id = sa.Column(GUID(), ForeignKey("documents.id",    ondelete="SET NULL"))
    file_uri    = sa.Column(sa.Text)
    label       = sa.Column(sa.Text)

    created_at, updated_at = ts_cols()

    meeting = relationship("Meeting", back_populates="meeting_documents")


