# src/OSSS/db/models/tutor.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class Tutor(UUIDMixin, Base):
    __tablename__ = "tutors"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=curriculum_instruction_assessment | ai_tutor_system; "
        "description=Stores AI tutor and human tutor records for the application. "
        "Key attributes include name, email, specialization. "
        "References related entities via: tutor_spec. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5+ column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment": (
            "Stores AI tutor and human tutor records for the application. "
            "Key attributes include name, email, specialization. "
            "References related entities via: tutor_spec. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores AI tutor and human tutor records for the application. "
                "Key attributes include name, email, specialization. "
                "References related entities via: tutor_spec."
            ),
        },
    }

    # Tutor fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    specialization: Mapped[Optional[str]] = mapped_column(Text)

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    # Relationships
    spec: Mapped[Optional["TutorSpec"]] = relationship(
        "TutorSpec", back_populates="tutor", uselist=False, cascade="all,delete-orphan"
    )
