# OSSS/db/models/attendance.py
from __future__ import annotations
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID
from typing import ClassVar

class Attendance(Base):
    __tablename__ = "attendance"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | student_services_school_level | teaching_instructional_support; "
        "description=Stores attendance records for the application. "
        "References related entities via: meeting, user. "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores attendance records for the application. "
            "References related entities via: meeting, user. "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores attendance records for the application. "
            "References related entities via: meeting, user. "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str | None] = mapped_column(sa.String(16))
    arrived_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    left_at: Mapped[sa.DateTime | None] = mapped_column(sa.TIMESTAMP(timezone=True))

    meeting: Mapped["Meeting"] = relationship("Meeting", lazy="joined")
    # user: Mapped["User"] = relationship("User", lazy="joined")  # if you want this
