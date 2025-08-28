# OSSS/db/models/scorecard_kpi.py
from __future__ import annotations
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID

class ScorecardKPI(Base):
    __tablename__ = "scorecard_kpis"

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

    __table_args__ = (
        sa.UniqueConstraint("scorecard_id", "kpi_id", name="uq_scorecard_kpis_pair"),
        # Optional: enforce unique display order within a scorecard when provided
        # sa.UniqueConstraint("scorecard_id", "display_order", name="uq_scorecard_kpis_order_per_scorecard"),
        # Or, if you only want uniqueness when display_order IS NOT NULL (preferred):
        # sa.Index("uq_scorecard_kpis_order_per_scorecard",
        #          "scorecard_id", "display_order",
        #          unique=True, postgresql_where=sa.text("display_order IS NOT NULL")),
    )
