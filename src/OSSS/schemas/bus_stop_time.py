from __future__ import annotations

from datetime import time
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .base import ORMBase


class BusStopTimeCreate(BaseModel):
    route_id: str = Field(..., description="FK to bus route")
    stop_id: str = Field(..., description="FK to bus stop")
    arrival_time: time = Field(..., description="Scheduled arrival time (HH:MM[:SS])")
    departure_time: Optional[time] = Field(
        None, description="Scheduled departure time; if omitted, same as arrival"
    )

    @field_validator("departure_time")
    @classmethod
    def _departure_not_before_arrival(cls, v: Optional[time], info):
        arrival = info.data.get("arrival_time")
        if v is not None and arrival is not None and v < arrival:
            raise ValueError("departure_time cannot be earlier than arrival_time")
        return v


class BusStopTimeOut(ORMBase):
    id: str
    route_id: str
    stop_id: str
    arrival_time: time
    departure_time: Optional[time] = None
    created_at: datetime
    updated_at: datetime
