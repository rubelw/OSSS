# src/OSSS/db/models/tutor_spec.py
from __future__ import annotations

from typing import Optional, Any, TYPE_CHECKING
import sqlalchemy as sa
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID

if TYPE_CHECKING:
    from .tutor import Tutor


class TutorSpec(UUIDMixin, Base):
    __tablename__ = "tutor_spec"
    __allow_unmapped__ = True  # keep NOTE strings (if any) out of the mapper

    # Keep UUIDMixin.id as the sole primary key. Do NOT declare another "id".
    tutor_id: Mapped[Any] = mapped_column(
        GUID(),
        ForeignKey("tutors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        unique=True,
    )

    # Example fields (adjust to your schema)
    spec_json: Mapped[Optional[dict]] = mapped_column(sa.JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit timestamps
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )

    # Relationships
    tutor: Mapped["Tutor"] = relationship(back_populates="spec")
