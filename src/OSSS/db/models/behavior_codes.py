# src/OSSS/db/models/behavior_codes.py
from __future__ import annotations

from sqlalchemy import Column, Text, TIMESTAMP, func

from .base import Base


class BehaviorCode(Base):
    __tablename__ = "behavior_codes"

    code = Column(Text, primary_key=True)
    description = Column(Text)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
