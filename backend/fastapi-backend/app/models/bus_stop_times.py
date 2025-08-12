from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from ._base import Base


class BusStopTime(Base):
    __tablename__ = "bus_stop_times"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    route_id = Column("route_id", UUID(as_uuid=True), ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    stop_id = Column("stop_id", UUID(as_uuid=True), ForeignKey("bus_stops.id", ondelete="CASCADE"), nullable=False)
    arrival_time = Column("arrival_time", Time, nullable=False)
    departure_time = Column("departure_time", Time)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    __table_args__ = (UniqueConstraint("route_id", "stop_id", "arrival_time", name="uq_bus_stop_time"), )
