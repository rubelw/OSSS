# models/message_recipient.py
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID

class MessageRecipient(Base):
    __tablename__ = "message_recipients"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    message_id: Mapped[str] = mapped_column(GUID(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id:  Mapped[str] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True)

    delivery_status: Mapped[str | None] = mapped_column(sa.Text)
    delivered_at:    Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

        sa.UniqueConstraint("message_id", "person_id", name="uq_message_recipients_pair"),
    )
