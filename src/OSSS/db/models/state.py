# src/OSSS/db/models/state.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from OSSS.db.base import Base

class State(Base):
    __tablename__ = "states"
    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
