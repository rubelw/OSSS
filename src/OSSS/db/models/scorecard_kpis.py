# OSSS/db/models/scorecard_kpi.py
from __future__ import annotations
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID
from typing import ClassVar

class ScorecardKPI(Base):
    __tablename__ = "scorecard_kpis"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores scorecard kpis records for the application. "
        "References related entities via: kpi, scorecard. "
        "4 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores scorecard kpis records for the application. "
            "References related entities via: kpi, scorecard. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores scorecard kpis records for the application. "
            "References related entities via: kpi, scorecard. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )

    scorecard_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("scorecards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kpi_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("kpis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_order: Mapped[int | None] = mapped_column(sa.Integer)

    scorecard: Mapped["Scorecard"] = relationship("Scorecard", back_populates="kpi_links", lazy="joined")
    kpi: Mapped["KPI"] = relationship("KPI", lazy="joined")
