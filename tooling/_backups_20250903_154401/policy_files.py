# OSSS/db/models/policy_file.py
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, GUID


class PolicyFile(Base):
    __tablename__ = "policy_files"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    policy_version = relationship("PolicyVersion", back_populates="files", lazy="selectin")
    file = relationship("File", back_populates="policy_links", lazy="selectin")

        sa.UniqueConstraint("policy_version_id", "file_id", name="uq_policy_files_pair"),
    )
