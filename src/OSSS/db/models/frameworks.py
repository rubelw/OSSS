
from __future__ import annotations

from typing import Optional, List, ClassVar
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSON


class Framework(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "frameworks"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment; "
        "description=Stores frameworks records for the application. "
        "Key attributes include code, name. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores frameworks records for the application. "
            "Key attributes include code, name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores frameworks records for the application. "
            "Key attributes include code, name. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    code: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    edition: Mapped[Optional[str]] = mapped_column(sa.String(64))
    effective_from: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    effective_to: Mapped[Optional[sa.Date]] = mapped_column(sa.Date)
    metadata_json = mapped_column("metadata", JSON, nullable=True)

    standards: Mapped[List["Standard"]] = relationship(
        "Standard",
        back_populates="framework",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

