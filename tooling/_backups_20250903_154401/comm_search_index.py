# OSSS/db/models/comm_search_index.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID, TSVectorType

class CommSearchIndex(Base):
    __tablename__ = "comm_search_index"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    entity_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    entity_id:   Mapped[str] = mapped_column(GUID(),       nullable=False, index=True)

    # Postgres tsvector column
    ts: Mapped[str | None] = mapped_column(TSVectorType())

        sa.UniqueConstraint("entity_type", "entity_id", name="uq_comm_search_index_pair"),
        sa.Index("ix_comm_search_index_ts", "ts", postgresql_using="gin"),
    )
