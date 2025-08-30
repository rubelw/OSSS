from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols


class Alignment(UUIDMixin, Base):
    __tablename__ = "alignments"

    curriculum_version_id: Mapped = mapped_column(GUID(), sa.ForeignKey("curriculum_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id: Mapped = mapped_column(GUID(), sa.ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)

    alignment_level: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="unknown")  # aligned|partial|not_aligned|unknown
    evidence_url: Mapped[str | None] = mapped_column(sa.String(512))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    created_at, updated_at = ts_cols()

    curriculum_version = relationship("CurriculumVersion", back_populates="alignments", lazy="joined")
    requirement = relationship("Requirement", back_populates="alignments", lazy="joined")
