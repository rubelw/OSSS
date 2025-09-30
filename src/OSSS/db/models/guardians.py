from __future__ import annotations

from datetime import datetime
from typing import Optional, ClassVar, TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, JSONB, GUID  # GUID = UUID column type

if TYPE_CHECKING:
    # Avoid import cycles at runtime
    from OSSS.db.models.userprofile import UserProfile


class Guardian(UUIDMixin, Base):
    __tablename__ = "guardians"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=student_services_school_level; "
        "description=Stores guardian linkages between students and their guardians. "
        "Fields include student_user_id, guardian_user_id (optional), guardian_email (optional). "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined (excluding relationships). "
        "Primary key is `id`."
    )

    __table_args__ = (
        Index("ix_guardian_student_email", "student_user_id", "guardian_email"),
        {
            "comment": (
                "Stores guardian linkages between students and their guardians. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "Composite index on (student_user_id, guardian_email)."
            ),
            "info": {
                "note": NOTE,
                "description": (
                    "Stores guardianship relationships linking a student to a guardian profile and/or email."
                ),
            },
        },
    )

    # Foreign keys to user_profiles.id (UUID/GUID)
    student_user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    guardian_user_id: Mapped[Optional[Any]] = mapped_column(
        GUID(), ForeignKey("user_profiles.id", ondelete="SET NULL"), nullable=True
    )

    # Optional guardian email (when there is no guardian_user_id profile, or as contact fallback)
    guardian_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    # Relationships (forward-declared via TYPE_CHECKING to avoid cycles)
    student: Mapped["UserProfile"] = relationship(
        "UserProfile",
        foreign_keys=[student_user_id],
        lazy="selectin",
    )
    guardian_profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        foreign_keys=[guardian_user_id],
        lazy="selectin",
    )

    # Audit timestamps (tz-aware, server-side defaults)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )
