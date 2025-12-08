from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Column, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID


class ConcessionSale(UUIDMixin, Base):
    __tablename__ = "concession_sales"

    stand_id: Mapped[str] = mapped_column(GUID(), ForeignKey("concession_stands.id"), nullable=False)
    event_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("events.id"))

    buyer_name: Mapped[str | None] = mapped_column(sa.String)
    buyer_email: Mapped[str | None] = mapped_column(sa.String)
    buyer_phone: Mapped[str | None] = mapped_column(sa.String)
    buyer_address_line1: Mapped[str | None] = mapped_column(sa.String)
    buyer_address_line2: Mapped[str | None] = mapped_column(sa.String)
    buyer_city: Mapped[str | None] = mapped_column(sa.String)
    buyer_state: Mapped[str | None] = mapped_column(sa.String)
    buyer_postal_code: Mapped[str | None] = mapped_column(sa.String)

    # A sale has many line items
    line_items: Mapped[list["ConcessionSaleItem"]] = relationship(
        "ConcessionSaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
    )

    # ✅ school_id as UUID FK to schools.id
    school_id: Mapped[str | None] = mapped_column(
        GUID(),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )