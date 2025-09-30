from __future__ import annotations

from datetime import datetime
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID

__all__ = ["TutorSession"]


class TutorSession(UUIDMixin, Base):
    __tablename__ = "sessions"
    __allow_unmapped__ = True

    NOTE: str = (
        "owner=curriculum_instruction_assessment | division_of_schools | ai_tutor_system; "
        "description=Represents a tutoring session context between a student and one or more AI tutors. "
        "References related entities via: students. "
        "Includes standard audit timestamps (created_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Represents a tutoring session context between a student and one or more AI tutors. "
            "References related entities via: students. "
            "Includes standard audit timestamps (created_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Represents a tutoring session context between a student and one or more AI tutors. "
                "References related entities via: students. "
                "Includes standard audit timestamps (created_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    # --- Columns ---
    student_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        sa.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subject: Mapped[str] = mapped_column(sa.Text, nullable=False)
    objective_code: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # --- Relationships ---
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="sessions",
        lazy="joined",
        passive_deletes=True,
    )
