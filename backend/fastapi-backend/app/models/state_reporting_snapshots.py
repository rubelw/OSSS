from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID, JSONB, UUIDMixin
import sqlalchemy as sa


class StateReportingSnapshot(UUIDMixin, Base):
    __tablename__ = "state_reporting_snapshots"
    as_of_date = Column("as_of_date", Date, nullable=False)
    scope = Column("scope", Text)
    payload = Column("payload", JSONB())
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
