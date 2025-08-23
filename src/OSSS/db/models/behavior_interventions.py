# src/OSSS/db/models/behavior_interventions.py
from __future__ import annotations

from sqlalchemy import Column, Text, Date, TIMESTAMP, ForeignKey, func

from .base import Base, GUID, UUIDMixin


class BehaviorIntervention(UUIDMixin, Base):
    __tablename__ = "behavior_interventions"

    student_id = Column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    intervention = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
