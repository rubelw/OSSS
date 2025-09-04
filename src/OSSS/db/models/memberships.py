# memberships.py
from __future__ import annotations

from datetime import date
from typing import Optional, ClassVar
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols


class Membership(UUIDMixin, Base):
    __tablename__ = "memberships"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=board_of_education_governing_board; "
        "description=Stores cic memberships records for the application. "
        "References related entities via: committee, person. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores cic memberships records for the application. "
            "References related entities via: committee, person. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores cic memberships records for the application. "
            "References related entities via: committee, person. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    # Foreign Keys / columns
    committee_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("committees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # IMPORTANT: your model registry defines the table as 'persons', not 'people'
    person_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[Optional[str]] = mapped_column(sa.Text)  # chair, member, etc.
    start_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    end_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    voting_member: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.sql.false()
    )

    # Relationships
    committee: Mapped["Committee"] = relationship("Committee", back_populates="memberships")
    # Add the next line only if you have a mapped Person class in your registry:
    # person: Mapped["Person"] = relationship("Person", back_populates="memberships")

    # Timestamps
    created_at, updated_at = ts_cols()