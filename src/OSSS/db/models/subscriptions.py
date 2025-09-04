# OSSS/db/models/subscription.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID
from typing import ClassVar

class Subscription(Base):
    __tablename__ = "subscriptions"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores subscriptions records for the application. "
        "References related entities via: channel, principal. "
        "Includes standard audit timestamps (created_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores subscriptions records for the application. "
            "References related entities via: channel, principal. "
            "Includes standard audit timestamps (created_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores subscriptions records for the application. "
            "References related entities via: channel, principal. "
            "Includes standard audit timestamps (created_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=text("gen_random_uuid()"))

    channel_id:     Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    principal_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # user|group|role
    principal_id:   Mapped[str] = mapped_column(GUID(), nullable=False, index=True)

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    channel = relationship("Channel", back_populates="subscriptions")
