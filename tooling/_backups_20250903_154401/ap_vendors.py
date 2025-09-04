from __future__ import annotations

from typing import Optional, Dict, Any
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, UUIDMixin, JSONB  # keep if JSONB is a cross-dialect alias; else use sa.JSON

class ApVendorBase:
    __abstract__ = True

    # Drop unique/index here if you keep the named UniqueConstraint below
    vendor_no: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    tax_id: Mapped[Optional[str]] = mapped_column(sa.String(64))

    # If JSONB isn’t cross-dialect in your project, replace JSONB() with sa.JSON()
    remit_to: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB(), nullable=True)
    contact:  Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB(), nullable=True)
    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB(), nullable=True)

    # Prefer Python-side default for portability; if you need server default: server_default=sa.text("1")
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

class ApVendor(ApVendorBase, UUIDMixin, Base):
    __tablename__ = "ap_vendors"
        sa.UniqueConstraint("vendor_no", name="uq_ap_vendors_vendor_no"),
    )
