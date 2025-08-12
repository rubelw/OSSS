from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base


class StudentTransportationAssignment(Base):
    __tablename__ = "student_transportation_assignments"
    id = Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    student_id = Column("student_id", UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    route_id = Column("route_id", UUID(as_uuid=True), ForeignKey("bus_routes.id", ondelete="SET NULL"))
    stop_id = Column("stop_id", UUID(as_uuid=True), ForeignKey("bus_stops.id", ondelete="SET NULL"))
    direction = Column("direction", Text)
    effective_start = Column("effective_start", Date, nullable=False)
    effective_end = Column("effective_end", Date)
    created_at = Column("created_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), server_default=text("now()"), nullable=False)
