# OSSS/db/models/attendance.py
from __future__ import annotations
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID

class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str | None] = mapped_column(sa.String(16))
    arrived_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    left_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))

    meeting: Mapped["Meeting"] = relationship("Meeting", lazy="joined")
    # user: Mapped["User"] = relationship("User", lazy="joined")  # if you want this

    __table_args__ = (
        sa.UniqueConstraint("meeting_id", "user_id", name="uq_attendance_meeting_user"),
        # Optional sanity check:
        sa.CheckConstraint("(left_at IS NULL) OR (arrived_at IS NULL) OR (left_at >= arrived_at)",
                           name="ck_attendance_left_after_arrived"),
    )
