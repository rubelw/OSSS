# app/user_models.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID as _UUID
from OSSS.db.base import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[_UUID] = mapped_column(GUID(), primary_key=True)
    username: Mapped[str] = mapped_column(sa.String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
