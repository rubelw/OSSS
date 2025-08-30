from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols


class Curriculum(UUIDMixin, Base):
    __tablename__ = "curricula"

    organization_id: Mapped = mapped_column(GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(sa.String(128))
    grade_range: Mapped[str | None] = mapped_column(sa.String(64))
    description: Mapped[str | None] = mapped_column(sa.Text)
    attributes: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    organization = relationship("Organization", back_populates="curricula", lazy="joined")
    versions = relationship("CurriculumVersion", back_populates="curriculum", cascade="all, delete-orphan")
