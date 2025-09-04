from __future__ import annotations
import uuid
from typing import Any, Optional, List, ClassVar
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TSVectorType

class DocumentSearchIndex(Base):
    __tablename__ = "document_search_index"
    __allow_unmapped__ = True  # keep NOTE out of mapper

    NOTE: ClassVar[str] = (
        "owner=division_of_technology_data; "
        "description=Stores document search index records for the application. "
        "References related entities via: document. "
        "2 column(s) defined. 1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores document search index records for the application. "
            "References related entities via: document. "
            "2 column(s) defined. 1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores document search index records for the application. "
                "References related entities via: document. "
                "2 column(s) defined. 1 foreign key field(s) detected."
            ),
        },
    }

    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    # With sqlalchemy-utils TSVectorType you can pass column names (e.g., TSVectorType('title'))
    # Our fallback maps to TSVECTOR on PG or TEXT elsewhere.
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    document: Mapped["Document"] = relationship("Document", back_populates="search_index", lazy="joined")

