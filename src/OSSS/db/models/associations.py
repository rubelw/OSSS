# OSSS/db/models/associations.py
from __future__ import annotations
import sqlalchemy as sa
from OSSS.db.base import Base, GUID

# Association table between curriculum_units and standards (M:N)
unit_standard_map = sa.Table(
    "unit_standard_map",
    Base.metadata,
    sa.Column(
        "unit_id",
        GUID(),
        sa.ForeignKey("curriculum_units.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "standard_id",
        GUID(),
        sa.ForeignKey("standards.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    comment="Joins curriculum_units to standards (M:N).",
    info={"description": "Association table between curriculum_units and standards."},
)

proposal_standard_map = sa.Table(
    "proposal_standard_map",
    Base.metadata,
    sa.Column("proposal_id", GUID(), sa.ForeignKey("proposals.id", ondelete="CASCADE"), primary_key=True, index=True),
    sa.Column("standard_id", GUID(), sa.ForeignKey("standards.id", ondelete="CASCADE"), primary_key=True, index=True),
    sa.UniqueConstraint("proposal_id", "standard_id", name="uq_proposal_standard_map"),
)

__all__ = ["unit_standard_map", "proposal_standard_map"]
