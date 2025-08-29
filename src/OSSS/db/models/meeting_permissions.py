from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols  # assuming this returns (created_at, updated_at)

class MeetingPermission(UUIDMixin, Base):
    __tablename__ = "meeting_permissions"

    meeting_id = sa.Column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    user_id = sa.Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    can_view = sa.Column(sa.Boolean, nullable=False, server_default=sa.sql.false())
    can_edit = sa.Column(sa.Text, nullable=False, server_default=text("0"))
    can_manage = sa.Column(sa.Text, nullable=False, server_default=text("0"))

    created_at, updated_at = ts_cols()

    __table_args__ = (
        UniqueConstraint("meeting_id", "user_id", name="uq_meeting_permissions_meeting_user"),
    )

    # Optional relationships if you have these models
    meeting = relationship("Meeting", back_populates="permissions", lazy="selectin")
    user = relationship("User", lazy="selectin")
