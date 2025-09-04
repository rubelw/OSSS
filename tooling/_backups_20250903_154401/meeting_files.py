# OSSS/db/models/meeting_file.py
from __future__ import annotations
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID

class MeetingFile(Base):
    __tablename__ = "meeting_files"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))
    meeting_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[uuid.UUID]   = mapped_column(GUID(), ForeignKey("files.id",    ondelete="CASCADE"), nullable=False, index=True)
    caption: Mapped[str | None]  = mapped_column(sa.String(255))

    meeting: Mapped["Meeting"] = relationship(
        "Meeting", back_populates="files", lazy="selectin", passive_deletes=True
    )

    file: Mapped["File"] = relationship(
        "File", back_populates="meeting_links", lazy="selectin", passive_deletes=True
    )
