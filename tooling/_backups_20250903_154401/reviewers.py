
from __future__ import annotations

from typing import Optional, List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID


class Reviewer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reviewers"

    association_id: Mapped[Optional[str]] = mapped_column(GUID(), index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.expression.true())

    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="reviewer")
