from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PersonAddress(Base):
    __tablename__ = "person_addresses"

    id: Mapped[Any] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True)
    address_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("addresses.id", ondelete="CASCADE"), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(sa.Text, nullable=False, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("person_id", "address_id", name="uq_person_addresses_person_address"),
    )