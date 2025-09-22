# src/OSSS/db/models/team_messages.py
from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from .common_enums import MessageChannel


class TeamMessage(UUIDMixin, Base):
    __tablename__ = "team_messages"

    team_id:   Mapped[str]                 = mapped_column(GUID(), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id: Mapped[str | None]          = mapped_column(GUID())  # user id (nullable if system-sent)
    channel:   Mapped[MessageChannel]      = mapped_column(Enum(MessageChannel, name="message_channel", native_enum=False), nullable=False)
    subject:   Mapped[str | None]          = mapped_column(sa.String(255))
    body:      Mapped[str | None]          = mapped_column(sa.Text)
    sent_at:   Mapped[datetime | None]     = mapped_column(sa.TIMESTAMP(timezone=True), default=datetime.utcnow)
    status:    Mapped[str | None]          = mapped_column(sa.String(32))  # queued, sent, failed

    # relationships
    team: Mapped["Team"] = relationship("Team")
