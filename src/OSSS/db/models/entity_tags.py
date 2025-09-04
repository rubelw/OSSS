# src/OSSS/db/models/entity_tags.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base

# Try to reuse your GUID type if you have one; else fall back to PG UUID
try:
    from OSSS.db.types import GUID  # your project’s custom GUID type, if present
    GUIDCol = GUID
except Exception:
    from sqlalchemy.dialects.postgresql import UUID as GUIDCol  # type: ignore

class EntityTag(Base):
    note: str = 'owner=division_of_technology_data; description=Stores entity tags records for the application. References related entities via: entity, tag. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.'

    __tablename__ = "entity_tags"
    __table_args__ = (
        # helpful for dedupe; keeps router happy with a simple surrogate PK
        sa.UniqueConstraint("entity_type", "entity_id", "tag_id", name="uq_entity_tags_triplet"),
        {
            "comment": (
                "Stores entity tags records for the application. References related entities via: entity, tag. "
                "Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. "
                "Primary key is `id`. 2 foreign key field(s) detected."
            ),
            "info": {
                "description": (
                    "Stores entity tags records for the application. References related entities via: entity, tag. "
                    "Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. "
                    "Primary key is `id`. 2 foreign key field(s) detected."
                )
            },
        },
    )

    id: Mapped[str] = mapped_column(
        GUIDCol, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    entity_type: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(GUIDCol, nullable=False, index=True)
    tag_id: Mapped[str] = mapped_column(GUIDCol, nullable=False, index=True)

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )
