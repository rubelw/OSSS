
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import Enum, DateTime
import enum

try:
    from OSSS.db.base import Base as OSSSBase  # type: ignore
    Base = OSSSBase
except Exception:
    Base = declarative_base()

try:
    from OSSS.db.mixins import TimestampMixin  # type: ignore
except Exception:
    class TimestampMixin:
        created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
        updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Level(str, enum.Enum):
    Varsity = "Varsity"
    JV = "JV"
    Freshman = "Freshman"
    MiddleSchool = "MiddleSchool"

class EventType(str, enum.Enum):
    Game = "Game"
    Practice = "Practice"
    Camp = "Camp"
    Fundraiser = "Fundraiser"
    Concession = "Concession"
    Other = "Other"

class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    refunded = "refunded"
    canceled = "canceled"

class AssignmentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    declined = "declined"
    completed = "completed"

class LiveStatus(str, enum.Enum):
    scheduled = "scheduled"
    live = "live"
    final = "final"
    canceled = "canceled"

class MessageChannel(str, enum.Enum):
    Email = "Email"
    SMS = "SMS"
    AppPush = "AppPush"
