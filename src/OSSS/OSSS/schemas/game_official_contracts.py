# src/OSSS/schemas/game_official_contracts.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from OSSS.db.models.game_official_contracts import GameOfficialContract
from OSSS.db.models.common_enums import AssignmentStatus


# ---------- Base ----------

class GameOfficialContractBase(BaseModel):
    """Shared fields for create/read."""
    game_id: UUID = Field(..., description="FK to games.id")
    official_id: UUID = Field(..., description="FK to officials.id")
    fee_cents: int | None = Field(None, ge=0, description="Fee in cents (non-negative)")
    contract_uri: str | None = Field(None, description="Optional URI to the contract")
    status: AssignmentStatus = Field(
        default=AssignmentStatus.pending, description="Assignment status"
    )
    signed_at: datetime | None = Field(None, description="When the contract was signed")


# ---------- Create / Update ----------

class GameOfficialContractCreate(GameOfficialContractBase):
    """Payload for create."""
    ...  # all required fields already in base


class GameOfficialContractUpdate(BaseModel):
    """Partial update (PATCH)."""
    fee_cents: int | None = Field(None, ge=0)
    contract_uri: str | None = None
    status: AssignmentStatus | None = None
    signed_at: datetime | None = None

    # If your API allows reassigning links, include these too:
    game_id: UUID | None = None
    official_id: UUID | None = None


# ---------- Read / DB ----------

class GameOfficialContractRead(GameOfficialContractBase):
    """Object returned by the API."""
    id: UUID

    # enable ORM-mode (Pydantic v2)
    model_config = ConfigDict(from_attributes=True)


# Optional: handy alias if your router expects these names
Model = GameOfficialContract
CreateSchema = GameOfficialContractCreate
UpdateSchema = GameOfficialContractUpdate
ReadSchema = GameOfficialContractRead
