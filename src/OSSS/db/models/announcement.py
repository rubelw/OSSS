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



class Announcement(UUIDMixin, Base):
    __tablename__ = "announcements"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    text: Mapped[Optional[str]] = mapped_column(Text)
    state: Mapped[PublicationState] = mapped_column(SQLEnum(PublicationState), default=PublicationState.PUBLISHED)
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    creation_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    course: Mapped[Course] = relationship(back_populates="announcements")
    materials: Mapped[list["Material"]] = relationship(back_populates="announcement", cascade="all,delete-orphan")

    user: Mapped["User"] = relationship("User", back_populates="annoucement")
