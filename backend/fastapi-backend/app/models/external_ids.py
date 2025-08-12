from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class ExternalId(Base):
    __tablename__ = "external_ids"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column("entity_type", Text, nullable=False)
    entity_id = Column("entity_id", GUID(), nullable=False)
    system = Column("system", Text, nullable=False)
    external_id = Column("external_id", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "system", name="uq_external_ids"), )
