from __future__ import annotations

import sqlalchemy as sa
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols, JSON


class Curriculum(UUIDMixin, Base):
    __tablename__ = "curricula"

    organization_id: Mapped = mapped_column(GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    proposal_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("proposals.id", ondelete="SET NULL"))

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(sa.String(128))
    grade_range: Mapped[str | None] = mapped_column(sa.String(64))
    description: Mapped[str | None] = mapped_column(sa.Text)
    attributes: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    organization = relationship("Organization", back_populates="curricula", lazy="joined")
    versions = relationship("CurriculumVersion", back_populates="curriculum", cascade="all, delete-orphan")

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(sa.Enum("draft", "adopted", "retired", name="curriculum_status", native_enum=False), nullable=False, server_default="draft")
    published_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))

    metadata_json = mapped_column("metadata", JSON, nullable=True)

    proposal = relationship("Proposal", back_populates="curriculum")
    units: Mapped[list["CurriculumUnit"]] = relationship(...)

