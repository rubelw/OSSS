from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class BusStopTime(Base):
    __tablename__ = "bus_stop_times"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column("route_id", GUID(), ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    stop_id = Column("stop_id", GUID(), ForeignKey("bus_stops.id", ondelete="CASCADE"), nullable=False)
    arrival_time = Column("arrival_time", Time, nullable=False)
    departure_time = Column("departure_time", Time)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("route_id", "stop_id", "arrival_time", name="uq_bus_stop_time"), )
