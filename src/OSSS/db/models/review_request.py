from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols


class ReviewRequest(UUIDMixin, Base):
    __tablename__ = "review_requests"

    curriculum_version_id: Mapped = mapped_column(GUID(), sa.ForeignKey("curriculum_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id: Mapped = mapped_column(GUID(), sa.ForeignKey("education_associations.id", ondelete="CASCADE"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="submitted")  # submitted|in_review|approved|rejected
    submitted_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))
    decided_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    created_at, updated_at = ts_cols()

    curriculum_version = relationship("CurriculumVersion", back_populates="reviews", lazy="joined")
    association = relationship("EducationAssociation", back_populates="reviews", lazy="joined")
