# models/document_notification.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID
from typing import ClassVar

class DocumentNotification(Base):
    __tablename__ = "document_notifications"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __allow_unmapped__ = True  # keep NOTE out of mapper

    NOTE: ClassVar[str] = (
        "owner=division_of_technology_data; "
        "description=Stores document notifications records for the application. "
        "References related entities via: document, user. "
        "5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores document notifications records for the application. "
            "References related entities via: document, user. "
            "5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores document notifications records for the application. "
                "References related entities via: document, user. "
                "5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
            ),
        },
    }

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id:     Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"),     nullable=False, index=True)

    subscribed:  Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.false())
    last_sent_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))

    document = relationship("Document", back_populates="notifications", lazy="joined")

