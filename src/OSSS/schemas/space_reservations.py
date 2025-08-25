# schemas/spacereservation.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel
from .base import ORMBase


class SpaceReservationCreate(BaseModel):
    space_id: str
    start_at: datetime
    end_at: datetime
    booked_by_user_id: Optional[str] = None
    purpose: Optional[str] = None
    status: str = "booked"
    setup: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None


class SpaceReservationOut(ORMBase):
    id: str
    space_id: str
    start_at: datetime
    end_at: datetime
    booked_by_user_id: Optional[str] = None
    purpose: Optional[str] = None
    status: str
    setup: Optional[Dict[str, Any]] = None
    attributes: O
