from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from .concession_items import ConcessionItem


class ConcessionSaleItem(UUIDMixin, Base):
    __tablename__ = "concession_sale_items"

    sale_id: Mapped[str] = mapped_column(GUID(), ForeignKey("concession_sales.id"), nullable=False)
    item_id: Mapped[str] = mapped_column(GUID(), ForeignKey("concession_items.id"), nullable=False)

    quantity: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    line_total_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    sale: Mapped["ConcessionSale"] = relationship(
        "ConcessionSale",
        back_populates="line_items",
    )
    item: Mapped[ConcessionItem] = relationship(
        "ConcessionItem",
        back_populates="sale_items",
    )
