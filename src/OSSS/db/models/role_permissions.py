# OSSS/db/models/role_permission.py
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID

class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    role_id: Mapped[str] = mapped_column(GUID(), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id: Mapped[str] = mapped_column(GUID(), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_pair"),
    )
