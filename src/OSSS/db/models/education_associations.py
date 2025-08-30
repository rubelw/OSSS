from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols


class EducationAssociation(UUIDMixin, Base):
    __tablename__ = "education_associations"

    name: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    contact: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    reviews = relationship("ReviewRequest", back_populates="association")
