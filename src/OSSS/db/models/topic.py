from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import sqlalchemy as sa
import uuid

from OSSS.db.base import Base, GUID, UUIDMixin, JSONB  # keep if JSONB is a cross-dialect alias; else use sa.JSON

class Topic(UUIDMixin, Base):
    __tablename__ = "topics"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    course: Mapped[Course] = relationship(back_populates="topics")

    __table_args__ = (
        UniqueConstraint("course_id", "name", name="uq_topic_course_name"),
    )

    # relationship back to User
    user: Mapped["User"] = relationship("User", back_populates="topic")