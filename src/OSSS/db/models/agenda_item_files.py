# models/agenda_item_file.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID
# from ._helpers import ts_cols  # if you want timestamps

class AgendaItemFile(Base):
    __tablename__ = "agenda_item_files"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    agenda_item_id: Mapped[str] = mapped_column(GUID(), ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id:        Mapped[str] = mapped_column(GUID(), ForeignKey("files.id",        ondelete="CASCADE"), nullable=False, index=True)
    caption:        Mapped[str | None] = mapped_column(sa.String(255))

    # created_at, updated_at = ts_cols()  # ← optional

    __table_args__ = (
        sa.UniqueConstraint("agenda_item_id", "file_id", name="uq_agenda_item_files_pair"),
    )
