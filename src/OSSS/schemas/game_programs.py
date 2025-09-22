from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ---------- Base ----------
class GameProgramBase(BaseModel):
    """
    Shared fields for GameProgram.
    """
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID
    program_uri: Optional[str] = None
    generated_at: Optional[datetime] = None  # server may set a default


# ---------- Create / Update ----------
class GameProgramCreate(GameProgramBase):
    """
    Fields accepted on create.
    - id/created_at/updated_at are server-assigned.
    """
    pass


class GameProgramUpdate(BaseModel):
    """
    Fields accepted on update (all optional/partial).
    """
    model_config = ConfigDict(from_attributes=True)

    game_id: Optional[UUID] = None
    program_uri: Optional[str] = None
    generated_at: Optional[datetime] = None


# ---------- Read ----------
class GameProgramRead(GameProgramBase):
    """
    Object returned from API.
    """
    id: UUID
    created_at: datetime
    updated_at: datetime


# ---------- Filter / List ----------
class GameProgramFilter(BaseModel):
    """
    Filter & pagination for list endpoints.
    `q` is a free-text search; typical backends apply it to text-like columns,
    e.g. program_uri.
    """
    # match by specific IDs
    id: Optional[List[UUID]] = None
    game_id: Optional[List[UUID]] = None

    # time range filters
    generated_at_from: Optional[datetime] = None
    generated_at_to: Optional[datetime] = None

    created_at_from: Optional[datetime] = None
    created_at_to: Optional[datetime] = None

    updated_at_from: Optional[datetime] = None
    updated_at_to: Optional[datetime] = None

    # free-text query (e.g., program_uri)
    q: Optional[str] = None

    # ordering / pagination
    order_by: Optional[List[str]] = None  # e.g., ["-created_at", "program_uri"]
    limit: int = 100
    offset: int = 0
