from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class BusStop(Base):
    __tablename__ = "bus_stops"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column("route_id", GUID(), ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    latitude = Column("latitude", Numeric(10,7))
    longitude = Column("longitude", Numeric(10,7))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
