# OSSS/db/models/feature_flag.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID
from typing import ClassVar

class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores feature flags records for the application. "
        "References related entities via: org. "
        "4 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores feature flags records for the application. "
            "References related entities via: org. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores feature flags records for the application. "
            "References related entities via: org. "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=text("gen_random_uuid()"))

    org_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False, index=True)
    key:    Mapped[str] = mapped_column(sa.String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Text, nullable=False, server_default=text("0"))
