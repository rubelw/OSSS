from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text

from sqlalchemy.orm import relationship
from .base import Base, GUID


class StudentTransportationAssignment(Base):
    __tablename__ = "student_transportation_assignments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    route_id = Column("route_id", GUID(), ForeignKey("bus_routes.id", ondelete="SET NULL"))
    stop_id = Column("stop_id", GUID(), ForeignKey("bus_stops.id", ondelete="SET NULL"))
    direction = Column("direction", Text)
    effective_start = Column("effective_start", Date, nullable=False)
    effective_end = Column("effective_end", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
