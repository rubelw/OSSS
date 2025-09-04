# OSSS/db/models/evaluation_file.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID

class EvaluationFile(Base):
    __tablename__ = "evaluation_files"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    assignment_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    file_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

        sa.UniqueConstraint("assignment_id", "file_id", name="uq_evaluation_files_pair"),
    )
