
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class ReviewerBase(BaseModel):
    association_id: Optional[uuid.UUID] = None
    name: str
    email: str
    active: Optional[bool] = True

    class Config:
        orm_mode = True


class ReviewerCreate(ReviewerBase): ...
class ReviewerUpdate(ReviewerBase): ...


class ReviewerRead(ReviewerBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
