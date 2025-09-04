# src/OSSS/db/models/states.py
from __future__ import annotations

from typing import List, ClassVar
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base

class State(Base):
    __tablename__ = "states"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores states records for the application. "
        "Key attributes include code, name. "
        "2 column(s) defined."
    )

    __table_args__ = {
        "comment":         (
            "Stores states records for the application. "
            "Key attributes include code, name. "
            "2 column(s) defined."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores states records for the application. "
            "Key attributes include code, name. "
            "2 column(s) defined."
        ),
        },
    }


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


