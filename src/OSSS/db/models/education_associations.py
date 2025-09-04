from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols
from typing import ClassVar


class EducationAssociation(UUIDMixin, Base):
    __tablename__ = "education_associations"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores education associations records for the application. "
        "Key attributes include name. "
        "Includes standard audit timestamps (created_at). "
        "5 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores education associations records for the application. "
            "Key attributes include name. "
            "Includes standard audit timestamps (created_at). "
            "5 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores education associations records for the application. "
            "Key attributes include name. "
            "Includes standard audit timestamps (created_at). "
            "5 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    name: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    contact: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at, updated_at = ts_cols()

    reviews = relationship("ReviewRequest", back_populates="association")


