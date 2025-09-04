from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols
from typing import ClassVar


class Requirement(UUIDMixin, Base):
    __tablename__ = "requirements"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores requirements records for the application. "
        "Key attributes include title. "
        "Includes standard audit timestamps (created_at). "
        "9 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores requirements records for the application. "
            "Key attributes include title. "
            "Includes standard audit timestamps (created_at). "
            "9 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores requirements records for the application. "
            "Key attributes include title. "
            "Includes standard audit timestamps (created_at). "
            "9 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    state_code: Mapped[str] = mapped_column(
        sa.String(2),
        sa.ForeignKey("states.code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(sa.String(128))
    description: Mapped[str | None] = mapped_column(sa.Text)
    effective_date: Mapped[sa.Date | None] = mapped_column(sa.Date)
    reference_url: Mapped[str | None] = mapped_column(sa.String(512))
    attributes: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    state = relationship("State", back_populates="requirements", lazy="joined")
    alignments = relationship("Alignment", back_populates="requirement", cascade="all, delete-orphan")


