
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class RoundDecisionBase(BaseModel):
    review_round_id: uuid.UUID
    decision: str
    decided_at: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        orm_mode = True


class RoundDecisionCreate(RoundDecisionBase): ...
class RoundDecisionUpdate(RoundDecisionBase): ...


class RoundDecisionRead(RoundDecisionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
