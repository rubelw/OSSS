from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID
from typing import ClassVar

class PersonContact(Base):
    __tablename__ = "person_contacts"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=student_services_school_level; "
        "description=Stores person contacts records for the application. "
        "References related entities via: contact, person. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores person contacts records for the application. "
            "References related entities via: contact, person. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores person contacts records for the application. "
            "References related entities via: contact, person. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    person_id:  Mapped[str] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(GUID(), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    label:      Mapped[str | None] = mapped_column(sa.Text)
    is_primary: Mapped[bool] = mapped_column(sa.Text, nullable=False, server_default=text("0"))
    is_emergency: Mapped[bool] = mapped_column(sa.Text, nullable=False, server_default=text("0"))

    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
