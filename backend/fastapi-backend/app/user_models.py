# app/user_models.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from uuid import UUID as _UUID
from .models.base import Base  # <-- share the same Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(sa.String(80), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False)
