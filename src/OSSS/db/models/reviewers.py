
from __future__ import annotations

from typing import Optional, List, ClassVar
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID


class Reviewer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reviewers"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores reviewers records for the application. "
        "Key attributes include name. "
        "References related entities via: association. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores reviewers records for the application. "
            "Key attributes include name. "
            "References related entities via: association. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores reviewers records for the application. "
            "Key attributes include name. "
            "References related entities via: association. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.expression.true())

    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="reviewer")