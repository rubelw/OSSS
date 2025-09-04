# models/agenda_item_file.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID
from typing import ClassVar
# from ._helpers import ts_cols  # if you want timestamps

class AgendaItemFile(Base):
    __tablename__ = "agenda_item_files"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores agenda item files records for the application. "
        "References related entities via: agenda item, file. "
        "4 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores agenda item files records for the application. "
            "References related entities via: agenda item, file. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores agenda item files records for the application. "
            "References related entities via: agenda item, file. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    agenda_item_id: Mapped[str] = mapped_column(GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id:        Mapped[str] = mapped_column(GUID(), ForeignKey("files.id",        ondelete="CASCADE"), nullable=False, index=True)
    caption:        Mapped[str | None] = mapped_column(sa.String(255))

    # created_at, updated_at = ts_cols()  # ← optional
