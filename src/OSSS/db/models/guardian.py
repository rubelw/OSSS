from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


from OSSS.db.base import Base, UUIDMixin, JSONB  # keep if JSONB is a cross-dialect alias; else use sa.JSON

class Guardian(UUIDMixin, Base):
    __tablename__ = "guardians"

    student_user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True)
    guardian_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user_profiles.id", ondelete="SET NULL"))
    guardian_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    student: Mapped[UserProfile] = relationship(foreign_keys=[student_user_id])
    guardian_profile: Mapped[Optional[UserProfile]] = relationship(foreign_keys=[guardian_user_id])

    __table_args__ = (Index("ix_guardian_student_email", "student_user_id", "guardian_email"),)

