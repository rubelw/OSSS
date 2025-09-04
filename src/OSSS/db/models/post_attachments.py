from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from typing import ClassVar

class PostAttachment(Base):
    __tablename__ = "post_attachments"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_communications_engagement; "
        "description=Stores post attachments records for the application. "
        "References related entities via: file, post. "
        "3 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores post attachments records for the application. "
            "References related entities via: file, post. "
            "3 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores post attachments records for the application. "
            "References related entities via: file, post. "
            "3 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    post_id: Mapped[str] = mapped_column(GUID(), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(GUID(), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="attachments")
