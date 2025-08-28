from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID

class PersonContact(Base):
    __tablename__ = "person_contacts"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    person_id:  Mapped[str] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(GUID(), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    label:      Mapped[str | None] = mapped_column(sa.Text)
    is_primary: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))
    is_emergency: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("person_id", "contact_id", name="uq_person_contacts_pair"),
    )
