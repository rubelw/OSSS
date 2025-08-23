# src/OSSS/db/models/incident_participants.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID


class IncidentParticipant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "incident_participants"

    incident_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(sa.Text, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("incident_id", "person_id", name="uq_incident_person"),
        sa.Index("ix_incident_participants_incident", "incident_id"),
        sa.Index("ix_incident_participants_person", "person_id"),
    )
