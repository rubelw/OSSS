# OSSS/db/models/feature_flag.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID

class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=text("gen_random_uuid()"))

    org_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    key:    Mapped[str] = mapped_column(sa.String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        sa.UniqueConstraint("org_id", "key", name="uq_feature_flags_org_key"),
        sa.Index("ix_feature_flags_org", "org_id"),
    )
