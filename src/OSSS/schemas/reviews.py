
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid


class ReviewBase(BaseModel):
    review_round_id: uuid.UUID
    reviewer_id: uuid.UUID
    status: Optional[str] = "draft"
    submitted_at: Optional[datetime] = None
    content: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True


class ReviewCreate(ReviewBase): ...
class ReviewUpdate(ReviewBase): ...


class ReviewRead(ReviewBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
