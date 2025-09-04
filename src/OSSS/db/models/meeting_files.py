# OSSS/db/models/meeting_file.py
from __future__ import annotations
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID
from typing import ClassVar

class MeetingFile(Base):
    __tablename__ = "meeting_files"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores meeting files records for the application. "
        "References related entities via: file, meeting. "
        "4 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores meeting files records for the application. "
            "References related entities via: file, meeting. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores meeting files records for the application. "
            "References related entities via: file, meeting. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


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


