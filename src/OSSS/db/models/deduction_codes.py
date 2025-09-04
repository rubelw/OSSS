from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class DeductionCode(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deduction_codes"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=business_accounting; "
        "description=Stores deduction codes records for the application. "
        "Key attributes include code, name. "
        "References related entities via: vendor. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores deduction codes records for the application. "
            "Key attributes include code, name. "
            "References related entities via: vendor. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores deduction codes records for the application. "
            "Key attributes include code, name. "
            "References related entities via: vendor. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)  # 403B, MED, etc.
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    pretax: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.true())
    vendor_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("vendors.id", ondelete="SET NULL"))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())


