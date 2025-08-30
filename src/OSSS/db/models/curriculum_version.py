from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols


class CurriculumVersion(UUIDMixin, Base):
    __tablename__ = "curriculum_versions"

    curriculum_id: Mapped = mapped_column(GUID(), sa.ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="draft")  # draft|submitted|approved|rejected
    submitted_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))
    decided_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    created_at, updated_at = ts_cols()

    curriculum = relationship("Curriculum", back_populates="versions", lazy="joined")
    reviews = relationship("ReviewRequest", back_populates="curriculum_version", cascade="all, delete-orphan")
    alignments = relationship("Alignment", back_populates="curriculum_version", cascade="all, delete-orphan")
