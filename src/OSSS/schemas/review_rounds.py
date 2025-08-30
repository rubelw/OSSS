
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class ReviewRoundBase(BaseModel):
    proposal_id: uuid.UUID
    round_no: int
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    status: Optional[str] = "open"

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,
    )


class ReviewRoundCreate(ReviewRoundBase): ...
class ReviewRoundUpdate(ReviewRoundBase): ...


class ReviewRoundRead(ReviewRoundBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
