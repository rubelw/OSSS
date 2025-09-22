# src/OSSS/db/models/concession_sale_items.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class ConcessionSaleItem(UUIDMixin, Base):
    __tablename__ = "concession_sale_items"

    sale_id:  Mapped[str] = mapped_column(
        GUID(), ForeignKey("concession_sales.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    item_id:  Mapped[str] = mapped_column(
        GUID(), ForeignKey("concession_items.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    quantity:    Mapped[int] = mapped_column(sa.Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # relationships
    sale: Mapped["ConcessionSale"]   = relationship("ConcessionSale", backref="line_items")
    item: Mapped["ConcessionItem"]   = relationship("ConcessionItem")
