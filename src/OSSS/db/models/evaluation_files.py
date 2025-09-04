# OSSS/db/models/evaluation_file.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID
from typing import ClassVar

class EvaluationFile(Base):
    __tablename__ = "evaluation_files"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores evaluation files records for the application. "
        "References related entities via: assignment, file. "
        "3 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores evaluation files records for the application. "
            "References related entities via: assignment, file. "
            "3 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores evaluation files records for the application. "
            "References related entities via: assignment, file. "
            "3 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    assignment_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    file_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
