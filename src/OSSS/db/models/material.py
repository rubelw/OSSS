from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .enums import *

from OSSS.db.base import Base, UUIDMixin, JSONB  # keep if JSONB is a cross-dialect alias; else use sa.JSON

class Material(UUIDMixin, Base):
    __tablename__ = "materials"

    type: Mapped[MaterialType] = mapped_column(SQLEnum(MaterialType), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    drive_file_id: Mapped[Optional[str]] = mapped_column(String(128))  # for DRIVE_FILE/FORM
    payload: Mapped[Optional[dict]] = mapped_column(JSON)  # extra provider-specific fields

    # link either to an announcement or coursework
    announcement_id: Mapped[Optional[int]] = mapped_column(ForeignKey("announcements.id", ondelete="CASCADE"))
    coursework_id: Mapped[Optional[int]] = mapped_column(ForeignKey("coursework.id", ondelete="CASCADE"))

    announcement: Mapped[Optional[Announcement]] = relationship(back_populates="materials")
    coursework: Mapped[Optional[CourseWork]] = relationship(back_populates="materials")

