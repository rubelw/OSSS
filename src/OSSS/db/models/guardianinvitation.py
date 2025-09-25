from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .enums import *
import sqlalchemy as sa
import uuid
from OSSS.db.base import Base, GUID, UUIDMixin, JSONB  # keep if JSONB is a cross-dialect alias; else use sa.JSON

class GuardianInvitation(UUIDMixin, Base):
    __tablename__ = "guardian_invitations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    student_user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True)
    invited_email: Mapped[str] = mapped_column(String(255))
    state: Mapped[GuardianInvitationState] = mapped_column(SQLEnum(GuardianInvitationState), default=GuardianInvitationState.PENDING)
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    student: Mapped[UserProfile] = relationship()
    user: Mapped["User"] = relationship("User", back_populates="guardianinvitation")

