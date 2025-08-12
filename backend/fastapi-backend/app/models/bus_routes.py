from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from .base import Base, GUID


class BusRoute(Base):
    __tablename__ = "bus_routes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column("name", Text, nullable=False)
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
