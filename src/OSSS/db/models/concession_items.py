from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
# Using string model names in relationships to avoid circular imports


class ConcessionItem(UUIDMixin, Base):
    __tablename__ = "concession_items"

    name: Mapped[str | None] = mapped_column(sa.String(255))
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    inventory_quantity: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    stand_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("concession_stands.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )

    # Many items belong to one stand
    stand: Mapped["ConcessionStand"] = relationship(
        "ConcessionStand",
        back_populates="items",
        foreign_keys="ConcessionItem.stand_id",
    )

    # One item can appear in many sale line items
    sale_items: Mapped[list["ConcessionSaleItem"]] = relationship(
        "ConcessionSaleItem",
        back_populates="item",
        cascade="all, delete-orphan",
    )

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False)

    school: Mapped["School"] = relationship(
        "School",
        back_populates="concession_items",
    )