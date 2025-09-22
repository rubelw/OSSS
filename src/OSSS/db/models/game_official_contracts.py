# src/OSSS/db/models/game_official_contracts.py
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from .common_enums import AssignmentStatus
from .games import Game
from .officials import Official


class GameOfficialContract(UUIDMixin, Base):
    __tablename__ = "game_official_contracts"

    game_id:     Mapped[str]              = mapped_column(GUID(), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    official_id: Mapped[str]              = mapped_column(GUID(), ForeignKey("officials.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_cents:   Mapped[int | None]       = mapped_column(sa.Integer)
    contract_uri: Mapped[str | None]      = mapped_column(sa.String(255))
    status:      Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignment_status", native_enum=False),
        nullable=False,
        default=AssignmentStatus.pending,
    )
    signed_at:   Mapped[datetime | None]  = mapped_column(sa.TIMESTAMP(timezone=True))

    # relationships
    game:     Mapped[Game]     = relationship("Game", backref="official_contracts")
    official: Mapped[Official] = relationship("Official")
