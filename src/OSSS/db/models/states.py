# src/OSSS/db/models/states.py
from __future__ import annotations

from typing import List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base

class State(Base):
    __tablename__ = "states"

    code: Mapped[str] = mapped_column(sa.String(2), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)

    # ⬇️ add this
    requirements: Mapped[List["Requirement"]] = relationship(
        "Requirement",
        back_populates="state",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"State(code={self.code!r}, name={self.name!r})"
