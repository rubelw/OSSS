from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, UUIDMixin, JSONB

# Import FastAPI/Pydantic schemas (ensure these files do NOT import this models module)
# This import is for FastAPI route typing / re-exports; models don't use them directly.
from OSSS.schemas.ap_vendors import (  # noqa: F401
    ApVendorCreate,
    ApVendorUpdate,
    ApVendorOut,
)


# ---------------------------
# ORM: mixin + concrete model
# ---------------------------

class ApVendorBase:  # mixin; not mapped
    __abstract__ = True

    vendor_no: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    tax_id: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)

    remit_to: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB(), nullable=True)
    contact:  Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB(), nullable=True)
    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB(), nullable=True)

    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))


class ApVendor(ApVendorBase, UUIDMixin, Base):  # concrete mapped class
    __tablename__ = "ap_vendors"
    __table_args__ = (sa.UniqueConstraint("vendor_no", name="uq_ap_vendors_vendor_no"),)


__all__ = ["ApVendor", "ApVendorBase"]
