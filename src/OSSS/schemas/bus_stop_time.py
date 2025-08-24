from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class BusStopTimeOut(ORMBase):
    id: str
    route_id: str
    stop_id: str
    arrival_time: time
    departure_time: Optional[time] = None
    created_at: datetime
    updated_at: datetime
