# models/document_notification.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID

class DocumentNotification(Base):
    __tablename__ = "document_notifications"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id:     Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"),     nullable=False, index=True)

    subscribed:  Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.false())
    last_sent_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))

    document = relationship("Document", back_populates="notifications", lazy="joined")

    __table_args__ = (
        sa.UniqueConstraint("document_id", "user_id", name="uq_document_notifications_pair"),
    )
