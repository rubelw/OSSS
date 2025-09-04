from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID

class PostAttachment(Base):
    __tablename__ = "post_attachments"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    post_id: Mapped[str] = mapped_column(GUID(), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[str] = mapped_column(GUID(), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="attachments")

        sa.UniqueConstraint("post_id", "file_id", name="uq_post_attachments_post_file"),
    )
