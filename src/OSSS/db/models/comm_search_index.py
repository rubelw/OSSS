# OSSS/db/models/comm_search_index.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID, TSVectorType
from typing import ClassVar

class CommSearchIndex(Base):
    __tablename__ = "comm_search_index"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_communications_engagement; "
        "description=Stores comm search index records for the application. "
        "References related entities via: entity. "
        "4 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores comm search index records for the application. "
            "References related entities via: entity. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores comm search index records for the application. "
            "References related entities via: entity. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    entity_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    entity_id:   Mapped[str] = mapped_column(GUID(),       nullable=False, index=True)

    # Postgres tsvector column
    ts: Mapped[str | None] = mapped_column(TSVectorType())
