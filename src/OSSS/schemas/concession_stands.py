# src/OSSS/schemas/concession_stands.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


__all__ = [
    "ConcessionStandBase",
    "ConcessionStandCreate",
    "ConcessionStandUpdate",
    "ConcessionStandRead",
]


class ConcessionStandBase(BaseModel):
    """Shared fields for ConcessionStand."""
    model_config = ConfigDict(from_attributes=True)

    school_id: UUID
    name: Optional[str] = None
    location: Optional[str] = None
    active: bool = True


class ConcessionStandCreate(ConcessionStandBase):
    """Payload for creating a ConcessionStand."""
    pass


class ConcessionStandUpdate(BaseModel):
    """Payload for partial updates to a ConcessionStand."""
    model_config = ConfigDict(from_attributes=True)

    school_id: Optional[UUID] = None
    name: Optional[str] = None
    location: Optional[str] = None
    active: Optional[bool] = None


class ConcessionStandRead(ConcessionStandBase):
    """Response model for ConcessionStand."""
    id: UUID
