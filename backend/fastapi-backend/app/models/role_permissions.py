from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column("role_id", GUID(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column("permission_id", GUID(), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
