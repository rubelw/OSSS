from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class BusStop(Base):
    __tablename__ = "bus_stops"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    route_id = Column("route_id", UUID(as_uuid=True), ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    latitude = Column("latitude", Numeric(10,7))
    longitude = Column("longitude", Numeric(10,7))
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
